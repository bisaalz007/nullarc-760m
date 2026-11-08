/* HOST TEST ONLY: no CoreFoundation objects or OS connection. */
#pragma once
#include <stdint.h>
typedef const void *CFTypeRef;
typedef const void *CFNumberRef;
#define CFSTR(s) (s)
#define kCFAllocatorDefault NULL
#define kCFNumberSInt64Type 4
static inline unsigned long CFGetTypeID(CFTypeRef p) { (void)p;return 1; }
static inline unsigned long CFNumberGetTypeID(void) { return 1; }
static inline int CFNumberGetValue(CFNumberRef p,int kind,void *out) {
    (void)p;(void)kind;*(int64_t *)out=512;return 1;
}
static inline void CFRelease(CFTypeRef p) { (void)p; }
