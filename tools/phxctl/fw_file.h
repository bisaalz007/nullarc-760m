/* SPDX-License-Identifier: MIT
 * Validate the whole firmware range before staging any bytes. This validates
 * file I/O only; firmware header/IP compatibility is a separate requirement.
 */
#ifndef PHX_FW_FILE_H
#define PHX_FW_FILE_H
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
static inline int phxParseUint32(const char *text, uint32_t *out) {
    if (!text || !*text || *text == '-' || *text == ' ' || *text == '\t') return 0;
    char *end = NULL; errno = 0;
    const unsigned long long value = strtoull(text, &end, 0);
    if (errno || !end || *end || value > UINT32_MAX) return 0;
    *out = (uint32_t)value; return 1;
}
static inline int phxFirmwareRange(FILE *f, uint32_t offset, uint32_t size) {
    if (!f || !size || fseeko(f, 0, SEEK_END)) return 0;
    const off_t length = ftello(f);
    if (length < 0 || offset > (uint64_t)length || size > (uint64_t)length - offset) return 0;
    return fseeko(f, offset, SEEK_SET) == 0;
}
#endif
