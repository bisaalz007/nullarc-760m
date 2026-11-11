// SPDX-License-Identifier: MIT
// Real offscreen readbacks for layouts observed in the HP WindowServer log.
@protocol NullArcTiledBuffer
- (id<MTLTexture>)newTiledTextureWithDescriptor:(MTLTextureDescriptor *)d offset:(NSUInteger)o bytesPerRow:(NSUInteger)r;
@end

static BOOL probeCompleted(id<MTLCommandBuffer> cb) {
    if (!cb) return NO;
    [cb commit]; [cb waitUntilCompleted];
    printf("regression command status %ld error %s\n",(long)cb.status,cb.error ? cb.error.localizedDescription.UTF8String : "none");
    return cb.status==MTLCommandBufferStatusCompleted && !cb.error;
}
static int textureLayoutTest(id<MTLDevice> dev) {
    const struct {NSUInteger w,h,row,off,size,bpp; MTLPixelFormat format; BOOL tiled;} cases[]={
        {17,23,128,0,4096,4,MTLPixelFormatBGRA8Unorm,YES},
        {84,103,192,0,20480,2,MTLPixelFormatR16Float,YES},
        {234,18,960,256,20480,4,MTLPixelFormatBGRA8Unorm,YES},
        {17,23,256,0,8192,4,MTLPixelFormatBGRA8Unorm,NO}};
    id<MTLCommandQueue> q=[dev newCommandQueue]; if(!q)return 20;
    for(NSUInteger k=0;k<sizeof(cases)/sizeof(cases[0]);++k) {@autoreleasepool {
        const NSUInteger w=cases[k].w,h=cases[k].h,row=cases[k].row,bpp=cases[k].bpp;
        id<MTLBuffer> b=[dev newBufferWithLength:cases[k].size options:MTLResourceStorageModeShared];
        id<MTLBuffer> out=[dev newBufferWithLength:row*h options:MTLResourceStorageModeShared];
        if(!b || !out || !b.contents || !out.contents)return 21;
        MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:cases[k].format width:w height:h mipmapped:NO];
        d.storageMode=MTLStorageModeShared; d.usage=MTLTextureUsageShaderRead;
        for(unsigned revision=0;revision<2;++revision) {@autoreleasepool {
            memset(b.contents,0xa5,b.length);memset(out.contents,0x5a,out.length);
            for(NSUInteger y=0;y<h;++y)for(NSUInteger x=0;x<w;++x){
                uint8_t *p=(uint8_t *)b.contents+cases[k].off+y*row+x*bpp;
                if(bpp==2){p[0]=(uint8_t)(x+revision);p[1]=0x38;} // finite half values
                else {p[0]=(uint8_t)(x+revision*53);p[1]=(uint8_t)(y*7);p[2]=(uint8_t)(x+y);p[3]=255;}
            }
            id<MTLTexture> t=nil;
            if(cases[k].tiled){
                if(![b respondsToSelector:@selector(newTiledTextureWithDescriptor:offset:bytesPerRow:)])return 22;
                t=[(id<NullArcTiledBuffer>)b newTiledTextureWithDescriptor:d offset:cases[k].off bytesPerRow:row];
            }else t=[b newTextureWithDescriptor:d offset:cases[k].off bytesPerRow:row];
            printf("texture case %lu: %lux%lu row %lu offset %lu revision %u: %s\n",(unsigned long)k,(unsigned long)w,(unsigned long)h,(unsigned long)row,(unsigned long)cases[k].off,revision,t?"created":"nil");
            if(!t)return 23;
            // Public aligned textures must remain aliases after creation.
            if(!cases[k].tiled)((uint8_t *)b.contents)[cases[k].off]^=0x3f;
            id<MTLCommandBuffer> cb=[q commandBuffer];id<MTLBlitCommandEncoder> be=[cb blitCommandEncoder];if(!be)return 24;
            [be copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(w,h,1)
                      toBuffer:out destinationOffset:0 destinationBytesPerRow:row destinationBytesPerImage:row*h];[be endEncoding];
            if(!probeCompleted(cb))return 25;
            for(NSUInteger y=0;y<h;++y)if(memcmp((uint8_t *)out.contents+y*row,(uint8_t *)b.contents+cases[k].off+y*row,w*bpp)){
                printf("texture case %lu: row %lu mismatch\n",(unsigned long)k,(unsigned long)y);return 26;}
        }}
    }}
    puts("PASS: observed tiled layouts, contents updates and aligned buffer alias read back correctly");return 0;
}

static NSString *const fetchSource=@"#include <metal_stdlib>\nusing namespace metal;\nstruct F {float4 pos [[position]];};\n"
 "vertex F fv(uint i [[vertex_id]]) { const float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};F v;v.pos=float4(p[i%3],0,1);return v;}\n"
 "fragment float4 ff(float4 old [[color(0)]]) {return float4(old.r+0.25f,old.g,old.b,1);}\n"
 "fragment float4 ff_sparse(float4 old [[color(0)]],float4 missing [[color(2)]]) {return float4(old.r+missing.r+0.25f,old.g,old.b,1);}\n";
static int fetchTest(id<MTLDevice> dev) {
    NSError *err=nil;id<MTLLibrary> lib=[dev newLibraryWithSource:fetchSource options:nil error:&err];
    if(!lib){printf("fetch library: %s\n",err.localizedDescription.UTF8String);return 30;}
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"fv"];pd.fragmentFunction=[lib newFunctionWithName:@"ff"];
    pd.colorAttachments[0].pixelFormat=MTLPixelFormatBGRA8Unorm;
    id<MTLRenderPipelineState> ps=[dev newRenderPipelineStateWithDescriptor:pd error:&err];if(!ps){printf("fetch pipeline: %s\n",err.localizedDescription.UTF8String);return 31;}
    id<MTLCommandQueue> q=[dev newCommandQueue];if(!q)return 32;
    const unsigned cases=getenv("NULLARC_PROBE_PLUGIN")?3:2;
    for(unsigned scenario=0;scenario<cases;++scenario){@autoreleasepool {
        const BOOL single=scenario==1;
        if(scenario==2){pd.fragmentFunction=[lib newFunctionWithName:@"ff_sparse"];
            ps=[dev newRenderPipelineStateWithDescriptor:pd error:&err];if(!ps){printf("sparse fetch pipeline: %s\n",err.localizedDescription.UTF8String);return 31;}}
        MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:64 height:64 mipmapped:NO];
        td.storageMode=MTLStorageModePrivate;td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
        id<MTLTexture> t=[dev newTextureWithDescriptor:td];id<MTLBuffer> out=[dev newBufferWithLength:64*64*4 options:MTLResourceStorageModeShared];if(!t||!out||!out.contents)return 32;
        memset(out.contents,0x55,out.length);
        MTLRenderPassDescriptor *rp=[MTLRenderPassDescriptor renderPassDescriptor];rp.colorAttachments[0].texture=t;rp.colorAttachments[0].loadAction=MTLLoadActionClear;
        rp.colorAttachments[0].clearColor=MTLClearColorMake(0,32.0/255.0,64.0/255.0,1);rp.colorAttachments[0].storeAction=MTLStoreActionStore;
        id<MTLCommandBuffer> cb=[q commandBuffer];id<MTLRenderCommandEncoder> re=[cb renderCommandEncoderWithDescriptor:rp];if(!re)return 33;
        [re setRenderPipelineState:ps];[re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:single?6:3];
        if(!single)[re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[re endEncoding];
        id<MTLBlitCommandEncoder> be=[cb blitCommandEncoder];if(!be)return 33;
        [be copyFromTexture:t sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,64,1)
                  toBuffer:out destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:16384];[be endEncoding];
        if(!probeCompleted(cb))return 34;
        NSUInteger bad=0;for(NSUInteger i=0;i<4096;++i){uint8_t *p=(uint8_t *)out.contents+i*4;
            if(abs((int)p[0]-64)>1||abs((int)p[1]-32)>1||abs((int)p[2]-128)>1||p[3]!=255)++bad;}
        printf("fetch %s: %lu/4096 correct, first 0x%08x\n",scenario==2?"missing attachment":single?"overlapping triangles":"two draws",(unsigned long)(4096-bad),*(uint32_t *)out.contents);
        if(bad)return 35;
    }}return 0;
}
static int allocationTest(id<MTLDevice> dev,unsigned count) {
    printf("recommended working set %llu bytes, unified %d\n",dev.recommendedMaxWorkingSetSize,dev.hasUnifiedMemory);
    if(getenv("NULLARC_PROBE_PLUGIN") && (!dev.hasUnifiedMemory || dev.recommendedMaxWorkingSetSize>512ull*1024*1024))return 41;
    NSMutableArray *textures=[NSMutableArray new];
    for(unsigned i=0;i<count;++i){@autoreleasepool {
        MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:1024 height:1024 mipmapped:NO];
        d.storageMode=MTLStorageModePrivate;d.usage=MTLTextureUsageShaderRead|MTLTextureUsageRenderTarget;
        id<MTLTexture> t=[dev newTextureWithDescriptor:d];if(!t){printf("allocation failed at %u textures (%u MiB of pixels)\n",i,i*4);return 40;}[textures addObject:t];
    }}
    printf("PASS: %lu concurrent 1024x1024 BGRA textures (%u MiB of pixels), %lu tracked bytes; no draw submitted\n",
           (unsigned long)textures.count,count*4,(unsigned long)dev.currentAllocatedSize);return textures.count==count?0:42;
}
