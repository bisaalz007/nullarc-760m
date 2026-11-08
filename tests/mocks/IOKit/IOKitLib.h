/* SPDX-License-Identifier: MIT
 * HOST TEST ONLY. No IOKit, kernel connection, registers or GPU execution.
 * Compile the actual mesboot.c against injected transport failures.
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <CoreFoundation/CFNumber.h>
#include "../../../src/amd/phx_memory_layout.h"
typedef uint32_t io_connect_t;
typedef uint32_t io_service_t;
typedef uint32_t kern_return_t;
#define kIOMainPortDefault 0
#define IO_OBJECT_NULL 0
#define kIOReturnNotReady 0xe00002d8u
#define kIOReturnBadArgument 0xe00002c2u
#define kIOReturnTimeout 0xe00002d6u
static inline uint32_t mach_task_self(void) { return 1; }
static inline void *IOServiceMatching(const char *name) { (void)name; return (void*)1; }
static inline io_service_t IOServiceGetMatchingService(uint32_t port,void *match) { (void)port;(void)match;return 1; }
static inline kern_return_t IOObjectRelease(io_service_t svc) { (void)svc;return 0; }
static inline kern_return_t IOServiceClose(io_connect_t c) { (void)c;return 0; }
static inline CFTypeRef IORegistryEntryCreateCFProperty(io_service_t svc,const char *key,void *allocator,uint32_t options) {
    (void)svc;(void)key;(void)allocator;(void)options;return (CFTypeRef)1;
}
static inline kern_return_t IOConnectCallStructMethod(io_connect_t c,uint32_t selector,
    const void *in,size_t size,void *out,size_t *n) {
    (void)c;(void)selector;(void)in;(void)size;(void)out;(void)n;return kIOReturnNotReady;
}
static inline kern_return_t IOServiceOpen(io_service_t svc,uint32_t task,uint32_t type,io_connect_t *c) {
    (void)svc;(void)task;(void)type;*c=1;return 0;
}
static inline int selected(const char *key,uint32_t selector) {
    const char *s=getenv(key);return s && strtoul(s,NULL,10)==selector;
}
static inline kern_return_t IOConnectCallScalarMethod(io_connect_t c,uint32_t selector,
    const uint64_t *in,uint32_t count,uint64_t *out,uint32_t *n) {
    (void)c;(void)in;(void)count;
    printf("test-call:%u\n",selector);
    if (selected("MESBOOT_TEST_FAIL",selector)) return 0xe00002bcu;
    if (out && n) memset(out,0,*n*sizeof(*out));
    if (n && selected("MESBOOT_TEST_SHORT",selector) && *n) --*n;
    return 0;
}
static inline kern_return_t IOConnectCallMethod(io_connect_t c,uint32_t selector,
    const uint64_t *in,uint32_t count,const void *bytes,size_t size,uint64_t *out,
    uint32_t *n,void *bout,size_t *bsize) {
    (void)c;(void)in;(void)count;(void)bytes;(void)size;(void)out;(void)n;
    printf("test-call:%u\n",selector);
    if (selected("MESBOOT_TEST_FAIL",selector)) return 0xe00002bcu;
    if (bout && bsize) memset(bout,0,*bsize);
    if (selector == PHX_SEL_MEMORY_LAYOUT && bout && bsize && *bsize == sizeof(struct phx_memory_layout)) {
        struct phx_memory_layout *p = bout;
        p->version = PHX_MEMORY_LAYOUT_VERSION; p->flags = PHX_MEMORY_DECODED;
        p->raw_base = 0x8000; p->raw_top = 0x817f; p->raw_offset = 0x6a0;
        p->mc_base = 0x8000000000ull; p->physical_base = 0x6a0000000ull;
        p->vram_bytes = 6ull << 30; p->cpu_aperture_base = 0x820400000ull; p->cpu_aperture_bytes = 256ull << 20;
        const char *mode = getenv("MESBOOT_TEST_MEMORY");
        if (mode && !strcmp(mode,"hp")) {
            p->flags |= PHX_MEMORY_DIAGNOSTIC_ONLY;
            p->raw_top = 0x801f; p->raw_offset = 0x260;
            p->physical_base = 0x260000000ull; p->vram_bytes = 512ull << 20;
        }
        if (mode && !strcmp(mode,"different")) { p->raw_offset = 0x260; p->physical_base = 0x260000000ull; }
        if (mode && !strcmp(mode,"invalid")) ++p->physical_base;
        if (mode && !strcmp(mode,"lost")) p->flags |= PHX_MEMORY_DEVICE_LOST;
    }
    if (bsize && selected("MESBOOT_TEST_SHORT",selector) && *bsize) --*bsize;
    return 0;
}
