// mtlprobe: Metal compute/render readback on PhxAccel + NVMTLDriver + RADV.
// The name is on NVMTLDriver's built-in allow list. Build: clang -fobjc-arc -framework Foundation -framework Metal
//   -framework IOKit -o mtlprobe mtlprobe.m; --hp requires the exact captured HP PCI identity.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#import <IOKit/IOKitLib.h>
#import <objc/runtime.h>
#include <dlfcn.h>
#include <limits.h>

// Match the accelerator's PCI ancestor, rather than choosing a device by name.
static BOOL hpNode(io_registry_entry_t node) {
    for (unsigned depth = 0; node && depth < 16; depth++) {
        if (IOObjectConformsTo(node, "IOPCIDevice")) {
            const char *keys[] = {"vendor-id", "device-id", "revision-id", "subsystem-vendor-id", "subsystem-id"};
            const uint32_t expected[] = {0x1002, 0x1900, 0xca, 0x103c, 0x8c6a};
            BOOL matches = YES;
            for (unsigned i = 0; i < 5; i++) {
                CFStringRef key = CFStringCreateWithCString(NULL, keys[i], kCFStringEncodingUTF8);
                CFTypeRef value = IORegistryEntryCreateCFProperty(node, key, kCFAllocatorDefault, 0);
                CFRelease(key);
                uint32_t number = 0;
                if (!value || CFGetTypeID(value) != CFDataGetTypeID() || CFDataGetLength(value) != 4) matches = NO;
                else { memcpy(&number, CFDataGetBytePtr(value), 4); if (number != expected[i]) matches = NO; }
                if (value) CFRelease(value);
            }
            IOObjectRelease(node);
            return matches;
        }
        io_registry_entry_t parent = IO_OBJECT_NULL;
        IORegistryEntryGetParentEntry(node, kIOServicePlane, &parent);
        IOObjectRelease(node);
        node = parent;
    }
    if (node) IOObjectRelease(node);
    return NO;
}
static BOOL hpDevice(id<MTLDevice> dev) {
    return [NSStringFromClass([dev class]) hasPrefix:@"NVMTL"] &&
        hpNode(IOServiceGetMatchingService(kIOMainPortDefault, IORegistryEntryIDMatching(dev.registryID)));
}

@protocol NullArcProbeDevice
- (instancetype)initWithAcceleratorPort:(mach_port_t)port;
@end
static NSArray<id<MTLDevice>> *isolatedDevices(const char *path) {
    // Test the candidate's own constructor without installing it or invoking
    // the Metal catalogue (which would also load the installed class).
    if (path[0]!='/' || objc_lookUpClass("NVMTLDevice")) return nil;
    if (!dlopen(path,RTLD_NOW|RTLD_LOCAL)) {fprintf(stderr,"candidate dlopen: %s\n",dlerror());return nil;}
    Class cls=objc_lookUpClass("NVMTLDevice");char requested[PATH_MAX],actual[PATH_MAX];
    const char *image=cls ? class_getImageName(cls) : NULL;
    if (!image || !realpath(path,requested) || !realpath(image,actual) || strcmp(requested,actual)) return nil;
    io_iterator_t it=IO_OBJECT_NULL;
    if (IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("NMXAccel"),&it)!=KERN_SUCCESS) return nil;
    io_service_t service=IOIteratorNext(it),extra=IOIteratorNext(it);IOObjectRelease(it);
    if (extra) {IOObjectRelease(extra);if(service)IOObjectRelease(service);return nil;}
    if (!service) return nil;
    IOObjectRetain(service);
    if (!hpNode(service)) {IOObjectRelease(service);return nil;}
    // Keep the service and image alive until this single-device probe exits.
    id<MTLDevice> dev=(id<MTLDevice>)[(id<NullArcProbeDevice>)[cls alloc] initWithAcceleratorPort:service];
    if (!dev) {IOObjectRelease(service);return nil;}
    printf("isolated NVMTL candidate: %s\n",actual);
    return @[dev];
}

static NSString *const kSrc =
    @"#include <metal_stdlib>\n"
     "using namespace metal;\n"
     "kernel void k(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) {\n"
     "    out[i] = i * 0x9E3779B1u + 7u;\n"
     "}\n";

// Render test: one triangle over the lower-left half of a 256x256 target cleared to blue, read back through a blit.
static NSString *const kGfxSrc =
    @"#include <metal_stdlib>\n"
     "using namespace metal;\n"
     "struct V { float4 pos [[position]]; float4 col; };\n"
     "vertex V vs(uint vid [[vertex_id]]) {\n"
     "    const float2 p[3] = { float2(-1, -1), float2(1, -1), float2(-1, 1) };\n"
     "    V o; o.pos = float4(p[vid], 0, 1); o.col = float4(1, 0, 0, 1); return o;\n"
     "}\n"
     "fragment float4 fs(V in [[stage_in]]) { return in.col; }\n";

static int renderTest(id<MTLDevice> dev) {
    NSError *err = nil;
    id<MTLLibrary> lib = [dev newLibraryWithSource:kGfxSrc options:nil error:&err];
    if (!lib) { printf("render library: %s\n", err.localizedDescription.UTF8String); return 12; }
    MTLRenderPipelineDescriptor *pd = [MTLRenderPipelineDescriptor new];
    pd.vertexFunction = [lib newFunctionWithName:@"vs"];
    pd.fragmentFunction = [lib newFunctionWithName:@"fs"];
    pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> ps = [dev newRenderPipelineStateWithDescriptor:pd error:&err];
    if (!ps) { printf("render pipeline: %s\n", err.localizedDescription.UTF8String); return 13; }
    const NSUInteger W = 256, H = 256;
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:W height:H mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
    td.storageMode = MTLStorageModePrivate;
    id<MTLTexture> rt = [dev newTextureWithDescriptor:td];
    id<MTLBuffer> out = [dev newBufferWithLength:W * H * 4 options:MTLResourceStorageModeShared];
    if (!rt || !out || !out.contents) return 15;
    memset(out.contents, 0x55, W * H * 4);
    id<MTLCommandQueue> q = [dev newCommandQueue];
    id<MTLCommandBuffer> cb = [q commandBuffer];
    if (!q || !cb) return 15;
    MTLRenderPassDescriptor *rp = [MTLRenderPassDescriptor renderPassDescriptor];
    rp.colorAttachments[0].texture = rt;
    rp.colorAttachments[0].loadAction = MTLLoadActionClear;
    rp.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 1, 1);
    rp.colorAttachments[0].storeAction = MTLStoreActionStore;
    id<MTLRenderCommandEncoder> re = [cb renderCommandEncoderWithDescriptor:rp];
    if (!re) return 15;
    [re setRenderPipelineState:ps];
    [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [re endEncoding];
    id<MTLBlitCommandEncoder> be = [cb blitCommandEncoder];
    if (!be) return 15;
    [be copyFromTexture:rt sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(W, H, 1)
               toBuffer:out destinationOffset:0 destinationBytesPerRow:W * 4 destinationBytesPerImage:W * H * 4];
    [be endEncoding];
    [cb commit];
    [cb waitUntilCompleted];
    printf("render command buffer status %ld error %s\n", (long)cb.status, cb.error ? cb.error.localizedDescription.UTF8String : "none");
    const uint32_t *px = out.contents;
    NSUInteger red = 0, blue = 0, other = 0;
    for (NSUInteger i = 0; i < W * H; i++) {
        if (px[i] == 0xFFFF0000u) red++; else if (px[i] == 0xFF0000FFu) blue++; else other++;
    }
    printf("pixels: red %lu blue %lu other %lu (expect ~32896 red, ~32640 blue); corners: TL 0x%08x BL 0x%08x BR 0x%08x\n",
           (unsigned long)red, (unsigned long)blue, (unsigned long)other, px[0], px[(H - 1) * W], px[H * W - 1]);
    return (cb.status == MTLCommandBufferStatusCompleted && !cb.error &&
            red > 30000 && blue > 30000 && !other && red + blue == W * H) ? 0 : 14;
}

#include "regressions.h"
int main(int argc, char **argv) {
    @autoreleasepool {
        BOOL hp = argc > 1 && !strcmp(argv[1], "--hp");
        const char *mode = argc > 1 + hp ? argv[1 + hp] : NULL;
        if (argc > 2 + hp || (mode && strcmp(mode, "list") && strcmp(mode, "render") && strcmp(mode,"textures") && strcmp(mode,"fetch") && strcmp(mode,"alloc") && strcmp(mode,"alloc-pressure"))) {
            fprintf(stderr, "usage: mtlprobe [--hp] [list|render|textures|fetch|alloc|alloc-pressure]\n"); return 2;
        }
        if (hp && (getenv("RADV_DARWIN_MOCK") || getenv("RADV_DARWIN_MOCK_PROFILE") || getenv("RADV_DARWIN_HOST_BO"))) {
            fprintf(stderr, "HP runtime test refuses mock and host-only transports\n"); return 2;
        }
        const char *candidate=getenv("NULLARC_PROBE_PLUGIN");
        if (candidate && !hp) return 2;
        NSArray<id<MTLDevice>> *all = candidate ? isolatedDevices(candidate) : MTLCopyAllDevices();
        if (candidate && !all) {fputs("candidate device creation failed; no installed-driver fallback\n",stderr);return 3;}
        printf("devices: %lu\n", (unsigned long)all.count);
        id<MTLDevice> dev = nil;
        for (id<MTLDevice> d in all) {
            printf("  %s  class=%s registryID=0x%llx lowPower=%d headless=%d\n", d.name.UTF8String,
                   object_getClassName(d), d.registryID, d.lowPower, d.headless);
            if (hp ? hpDevice(d) : [NSStringFromClass([d class]) hasPrefix:@"NVMTL"]) dev = d;
        }
        if (!dev && !hp) dev = MTLCreateSystemDefaultDevice();
        // EX_TEMPFAIL only for an empty catalogue; wrong-device and other errors
        // remain fatal. Boot matching publishes the accelerator asynchronously.
        if (!dev) { printf("no Metal device\n"); return hp && !all.count ? 75 : 1; }
        printf("using %s\n", dev.name.UTF8String);
        if (hp) printf("HP PCI identity verified: 1002:1900 ca 103c:8c6a; no device fallback\n");
        if (mode && !strcmp(mode, "list")) return 0;

        if (mode && !strcmp(mode, "render")) return renderTest(dev);
        if (mode && !strcmp(mode,"textures")) return textureLayoutTest(dev);
        if (mode && !strcmp(mode,"fetch")) return fetchTest(dev);
        if (mode && !strcmp(mode,"alloc")) return allocationTest(dev,32);
        if (mode && !strcmp(mode,"alloc-pressure")) return hp ? allocationTest(dev,80) : 2;
        NSError *err = nil;
        id<MTLLibrary> lib = [dev newLibraryWithSource:kSrc options:nil error:&err];
        if (!lib) { printf("library: %s\n", err.localizedDescription.UTF8String); return 2; }
        id<MTLFunction> fn = [lib newFunctionWithName:@"k"];
        id<MTLComputePipelineState> ps = [dev newComputePipelineStateWithFunction:fn error:&err];
        if (!ps) { printf("pipeline: %s\n", err.localizedDescription.UTF8String); return 3; }
        const NSUInteger n = 4096;
        id<MTLBuffer> buf = [dev newBufferWithLength:n * 4 options:MTLResourceStorageModeShared];
        if (!buf || !buf.contents) return 5;
        memset(buf.contents, 0, n * 4);
        id<MTLCommandQueue> q = [dev newCommandQueue];
        id<MTLCommandBuffer> cb = [q commandBuffer];
        id<MTLComputeCommandEncoder> enc = [cb computeCommandEncoder];
        if (!q || !cb || !enc) return 5;
        [enc setComputePipelineState:ps];
        [enc setBuffer:buf offset:0 atIndex:0];
        [enc dispatchThreads:MTLSizeMake(n, 1, 1) threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
        [enc endEncoding];
        [cb commit];
        [cb waitUntilCompleted];
        printf("command buffer status %ld error %s\n", (long)cb.status, cb.error ? cb.error.localizedDescription.UTF8String : "none");
        const uint32_t *o = buf.contents;
        NSUInteger ok = 0;
        for (NSUInteger i = 0; i < n; i++) ok += o[i] == (uint32_t)(i * 0x9E3779B1u + 7u);
        printf("results: %lu/%lu correct (out[1]=0x%08x, expected 0x%08x)\n", (unsigned long)ok, (unsigned long)n, o[1],
               (uint32_t)(0x9E3779B1u + 7u));
        return ok == n && cb.status == MTLCommandBufferStatusCompleted && !cb.error ? 0 : 4;
    }
}
