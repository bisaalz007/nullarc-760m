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
typedef uint32_t io_connect_t;
typedef uint32_t io_service_t;
typedef uint32_t kern_return_t;
#define kIOMainPortDefault 0
#define kIOReturnBadArgument 0xe00002c2u
#define kIOReturnTimeout 0xe00002d6u
static inline uint32_t mach_task_self(void) { return 1; }
static inline void *IOServiceMatching(const char *name) { (void)name; return (void*)1; }
static inline io_service_t IOServiceGetMatchingService(uint32_t port,void *match) { (void)port;(void)match;return 1; }
static inline kern_return_t IOObjectRelease(io_service_t svc) { (void)svc;return 0; }
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
    if (bsize && selected("MESBOOT_TEST_SHORT",selector) && *bsize) --*bsize;
    return 0;
}
