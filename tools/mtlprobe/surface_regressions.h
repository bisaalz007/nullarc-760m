// SPDX-License-Identifier: MIT
// Exercise IOSurface visibility and resource destruction with bounded GPU work.
static int surfaceTest(id<MTLDevice> device)
{
    const NSUInteger widths[] = {64, 161, 1920};
    const NSUInteger heights[] = {64, 161, 1200};
    id<MTLCommandQueue> queue = [device newCommandQueue];
    if (!queue) return 50;
    for (unsigned test = 0; test < 3; test++) { @autoreleasepool {
        const NSUInteger width = widths[test], height = heights[test];
        NSDictionary *properties = @{
            (__bridge NSString *)kIOSurfaceWidth: @(width),
            (__bridge NSString *)kIOSurfaceHeight: @(height),
            (__bridge NSString *)kIOSurfaceBytesPerElement: @4,
            (__bridge NSString *)kIOSurfacePixelFormat: @(0x42475241u)
        };
        IOSurfaceRef surface = IOSurfaceCreate((__bridge CFDictionaryRef)properties);
        if (!surface) return 51;
        // ARC retains this owner through the end of the iteration.
        __attribute__((objc_precise_lifetime)) id surfaceOwner = CFBridgingRelease(surface);
        surface = (__bridge IOSurfaceRef)surfaceOwner;
        const NSUInteger pitch = IOSurfaceGetBytesPerRow(surface);
        MTLTextureDescriptor *descriptor = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
            width:width height:height mipmapped:NO];
        descriptor.storageMode = MTLStorageModeShared;
        descriptor.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead;
        id<MTLTexture> texture = [device newTextureWithDescriptor:descriptor iosurface:surface plane:0];
        id<MTLTexture> alias = [device newTextureWithDescriptor:descriptor iosurface:surface plane:0];
        id<MTLBuffer> output = [device newBufferWithLength:pitch * height options:MTLResourceStorageModeShared];
        if (!texture || !alias || !output.contents) return 52;
        for (unsigned revision = 0; revision < 3; revision++) { @autoreleasepool {
            const uint32_t expected = revision == 1 ? 0xff00ff00u : 0xffff0000u;
            MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
            pass.colorAttachments[0].texture = texture;
            pass.colorAttachments[0].loadAction = MTLLoadActionClear;
            pass.colorAttachments[0].storeAction = MTLStoreActionStore;
            pass.colorAttachments[0].clearColor = revision == 1
                ? MTLClearColorMake(0, 1, 0, 1) : MTLClearColorMake(1, 0, 0, 1);
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
            if (!encoder) return 53;
            [encoder endEncoding];
            id<MTLBlitCommandEncoder> blit = [command blitCommandEncoder];
            if (!blit) return 53;
            [blit copyFromTexture:alias sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
                sourceSize:MTLSizeMake(width, height, 1) toBuffer:output destinationOffset:0
                destinationBytesPerRow:pitch destinationBytesPerImage:pitch * height];
            [blit endEncoding];
            if (!probeCompleted(command)) return 54;
            if (IOSurfaceLock(surface, kIOSurfaceLockReadOnly, NULL) != kIOReturnSuccess) return 55;
            const uint8_t *cpu = IOSurfaceGetBaseAddress(surface);
            if (!cpu) {
                IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, NULL);
                return 55;
            }
            NSUInteger wrong = 0;
            for (NSUInteger y = 0; y < height; y++) {
                const uint32_t *row = (const uint32_t *)(cpu + y * pitch);
                const uint32_t *gpu = (const uint32_t *)((const uint8_t *)output.contents + y * pitch);
                for (NSUInteger x = 0; x < width; x++) {
                    if (row[x] != expected || gpu[x] != expected) wrong++;
                }
            }
            IOSurfaceUnlock(surface, kIOSurfaceLockReadOnly, NULL);
            printf("IOSurface GPU-to-CPU and alias %lux%lu pitch %lu revision %u: %lu mismatches\n",
                (unsigned long)width, (unsigned long)height, (unsigned long)pitch, revision, (unsigned long)wrong);
            if (wrong) return 56;
        }}
        if (IOSurfaceLock(surface, 0, NULL) != kIOReturnSuccess) return 55;
        uint8_t *cpu = IOSurfaceGetBaseAddress(surface);
        if (!cpu) {
            IOSurfaceUnlock(surface, 0, NULL);
            return 55;
        }
        for (NSUInteger y = 0; y < height; y++) {
            uint32_t *row = (uint32_t *)(cpu + y * pitch);
            for (NSUInteger x = 0; x < width; x++) row[x] = 0xff804020u ^ (uint32_t)((x + y) & 255);
        }
        IOSurfaceUnlock(surface, 0, NULL);
        memset(output.contents, 0, output.length);
        id<MTLCommandBuffer> command = [queue commandBuffer];
        id<MTLBlitCommandEncoder> blit = [command blitCommandEncoder];
        if (!blit) return 53;
        [blit copyFromTexture:alias sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0, 0, 0)
            sourceSize:MTLSizeMake(width, height, 1) toBuffer:output destinationOffset:0
            destinationBytesPerRow:pitch destinationBytesPerImage:pitch * height];
        [blit endEncoding];
        if (!probeCompleted(command)) return 54;
        for (NSUInteger y = 0; y < height; y++) {
            const uint32_t *row = (const uint32_t *)((const uint8_t *)output.contents + y * pitch);
            for (NSUInteger x = 0; x < width; x++) {
                if (row[x] != (0xff804020u ^ (uint32_t)((x + y) & 255))) return 57;
            }
        }
        printf("IOSurface CPU-to-GPU %lux%lu: all pixels match\n", (unsigned long)width, (unsigned long)height);
    }}
    return 0;
}

static int lifetimeTest(id<MTLDevice> device, BOOL churn)
{
    id<MTLCommandQueue> queue = [device newCommandQueue];
    if (!queue) return 60;
    // Hold eight submissions at once while discarding their source wrappers.
    const NSUInteger length = churn ? 1024 * 1024 : 256 * 1024;
    for (unsigned batch = 0; batch < 16; batch++) { @autoreleasepool {
        NSMutableArray<id<MTLCommandBuffer>> *commands = [NSMutableArray new];
        NSMutableArray<id<MTLBuffer>> *outputs = [NSMutableArray new];
        for (unsigned index = 0; index < 8; index++) { @autoreleasepool {
            id<MTLBuffer> temporary = [device newBufferWithLength:length options:MTLResourceStorageModePrivate];
            id<MTLBuffer> output = [device newBufferWithLength:length options:MTLResourceStorageModeShared];
            if (!temporary || !output.contents) return 61;
            id<MTLBuffer> unrelated = nil;
            if (churn) {
                unrelated = [device newBufferWithLength:8 * 1024 * 1024 options:MTLResourceStorageModePrivate];
                if (!unrelated) return 65;
            }
            memset(output.contents, 0, length);
            id<MTLCommandBuffer> command = [queue commandBuffer];
            id<MTLBlitCommandEncoder> blit = [command blitCommandEncoder];
            if (!blit) return 62;
            [blit fillBuffer:temporary range:NSMakeRange(0, length) value:(uint8_t)(batch * 8 + index + 1)];
            [blit copyFromBuffer:temporary sourceOffset:0 toBuffer:output destinationOffset:0 size:length];
            [blit endEncoding];
            [commands addObject:command];
            [outputs addObject:output];
            [command commit];
            // This allocation was never referenced by a GPU command. Vulkan
            // permits its destruction while other resources are in flight.
            unrelated = nil;
        }}
        for (unsigned index = 0; index < 8; index++) {
            id<MTLCommandBuffer> command = commands[index];
            [command waitUntilCompleted];
            if (command.status != MTLCommandBufferStatusCompleted || command.error) return 63;
            const uint8_t *bytes = outputs[index].contents;
            const uint8_t expected = (uint8_t)(batch * 8 + index + 1);
            for (NSUInteger offset = 0; offset < length; offset++) if (bytes[offset] != expected) return 64;
        }
    }}
    puts("PASS: 128 asynchronous fill/copy submissions survived source-wrapper release; every byte matched");
    if (churn) puts("PASS: 128 unrelated 8 MiB allocations were destroyed during queued work");
    return 0;
}
