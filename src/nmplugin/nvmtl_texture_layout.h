/* SPDX-License-Identifier: MIT */
#ifndef NVMTL_TEXTURE_LAYOUT_H
#define NVMTL_TEXTURE_LAYOUT_H
#include <stddef.h>

/* Source ends at the last pixel/block, not at the last row's padding. */
static inline int nvmtl_rows_fit(size_t size, size_t offset, size_t pitch, size_t rows, size_t active)
{
    if (!rows || !active || pitch < active || offset > size || active > size - offset) return 0;
    return rows - 1 <= (size - offset - active) / pitch;
}
#endif
