/* SPDX-License-Identifier: MIT
 * Exercise the actual plugin's metallib reader and translator. No MTLDevice is
 * constructed, and no Vulkan commands or hardware connections are requested.
 */
#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc != 4) return 2;
        void *bundle = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
        if (!bundle) { fprintf(stderr, "%s\n", dlerror()); return 1; }
        typedef NSDictionary *(*translate_fn)(NSData *, NSDictionary **, NSDictionary **);
        translate_fn translate = (translate_fn)dlsym(bundle, "nvmtl_translate_metallib");
        if (!translate) return 1;
        NSData *input = [NSData dataWithContentsOfFile:@(argv[2])];
        NSDictionary *stages = nil, *air = nil;
        NSDictionary *functions = translate(input, &stages, &air);
        typedef NSData *(*compile_fn)(NSData *, NSString *, NSString *, NSString *, NSString **);
        compile_fn compile = (compile_fn)dlsym(bundle, "nvmtl_compile_library_entry");
        if (!compile || !functions[@"store_value"] || !air[@"store_value"]) {
            fprintf(stderr, "metallib index/IR extraction failed\n"); return 1;
        }
        NSString *error = nil;
        NSData *spirv = compile(functions[@"store_value"], air[@"store_value"], stages[@"store_value"], @"store_value", &error);
        if (!spirv || spirv.length < 20 || spirv.length % 4 ||
            *(const uint32_t *)spirv.bytes != 0x07230203 ||
            ![stages[@"store_value"] isEqualToString:@"kernel"] || !air[@"store_value"]) {
            fprintf(stderr, "metallib store_value translation failed: %s\n", error.UTF8String ?: "missing stage or SPIR-V"); return 1;
        }
        if (![spirv writeToFile:@(argv[3]) atomically:YES]) return 1;
        for (NSString *name in @[@"triangle_vertex", @"solid_fragment"]) {
            NSString *stage = [name isEqualToString:@"triangle_vertex"] ? @"vertex" : @"fragment";
            if (![stages[name] isEqualToString:stage] || !functions[name] || !air[name]) return 1;
            NSData *translated = compile(functions[name], air[name], stage, name, &error);
            if (!translated || translated.length < 20 || *(const uint32_t *)translated.bytes != 0x07230203) {
                fprintf(stderr, "%s translation failed: %s\n", name.UTF8String, error.UTF8String ?: "no SPIR-V"); return 1;
            }
            NSString *path = [[@(argv[3]) stringByDeletingLastPathComponent] stringByAppendingPathComponent:[name stringByAppendingString:@".spv"]];
            if (![translated writeToFile:path atomically:YES]) return 1;
            printf("[PASS] metallib %s -> %s SPIR-V (%lu bytes)\n", name.UTF8String, stage.UTF8String, (unsigned long)translated.length);
        }
        printf("[PASS] compiled MSL metallib -> plugin AIR reader -> SPIR-V (%lu bytes); no GPU execution\n", (unsigned long)spirv.length);
        // The plugin has process-lifetime caches and blocks; let process exit
        // unload it after their lifetime instead of manually calling dlclose.
    }
    return 0;
}
