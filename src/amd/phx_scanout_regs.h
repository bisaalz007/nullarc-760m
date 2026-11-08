/*
 * Copyright 2022 Advanced Micro Devices, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
 * THE COPYRIGHT HOLDER(S) OR AUTHOR(S) BE LIABLE FOR ANY CLAIM, DAMAGES OR
 * OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
 * ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
 * OTHER DEALINGS IN THE SOFTWARE.
 *
 */
/* SPDX-License-Identifier: MIT */
/* SPDX-License-Identifier: MIT
 * Read-only DCN 3.1.4 register addresses from Linux v6.14.
 * Segment bases measured on the exact HP 760M profile.
 * See hardware/profiles/hp-760m-scanout-registers.json for provenance.
 */
#ifndef PHX_SCANOUT_REGS_H
#define PHX_SCANOUT_REGS_H
#include <stdint.h>
struct phx_scanout_register { const char *name; uint32_t dword; };
static const struct phx_scanout_register phx_scanout_registers[] = {
    {"regHUBP0_DCSURF_SURFACE_CONFIG", 0x3aa5u},
    {"regHUBP0_DCSURF_ADDR_CONFIG", 0x3aa6u},
    {"regHUBP0_DCSURF_TILING_CONFIG", 0x3aa7u},
    {"regHUBP0_DCSURF_PRI_VIEWPORT_DIMENSION", 0x3aaau},
    {"regHUBP0_DCHUBP_CNTL", 0x3ab3u},
    {"regHUBPREQ0_DCSURF_SURFACE_PITCH", 0x3ac7u},
    {"regHUBPREQ0_DCSURF_PRIMARY_SURFACE_ADDRESS", 0x3acau},
    {"regHUBPREQ0_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH", 0x3acbu},
    {"regHUBPREQ0_DCSURF_SECONDARY_SURFACE_ADDRESS", 0x3aceu},
    {"regHUBPREQ0_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH", 0x3acfu},
    {"regHUBPREQ0_DCSURF_PRIMARY_META_SURFACE_ADDRESS", 0x3ad2u},
    {"regHUBPREQ0_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH", 0x3ad3u},
    {"regHUBP1_DCSURF_SURFACE_CONFIG", 0x3b81u},
    {"regHUBP1_DCSURF_ADDR_CONFIG", 0x3b82u},
    {"regHUBP1_DCSURF_TILING_CONFIG", 0x3b83u},
    {"regHUBP1_DCSURF_PRI_VIEWPORT_DIMENSION", 0x3b86u},
    {"regHUBP1_DCHUBP_CNTL", 0x3b8fu},
    {"regHUBPREQ1_DCSURF_SURFACE_PITCH", 0x3ba3u},
    {"regHUBPREQ1_DCSURF_PRIMARY_SURFACE_ADDRESS", 0x3ba6u},
    {"regHUBPREQ1_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH", 0x3ba7u},
    {"regHUBPREQ1_DCSURF_SECONDARY_SURFACE_ADDRESS", 0x3baau},
    {"regHUBPREQ1_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH", 0x3babu},
    {"regHUBPREQ1_DCSURF_PRIMARY_META_SURFACE_ADDRESS", 0x3baeu},
    {"regHUBPREQ1_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH", 0x3bafu},
    {"regHUBP2_DCSURF_SURFACE_CONFIG", 0x3c5du},
    {"regHUBP2_DCSURF_ADDR_CONFIG", 0x3c5eu},
    {"regHUBP2_DCSURF_TILING_CONFIG", 0x3c5fu},
    {"regHUBP2_DCSURF_PRI_VIEWPORT_DIMENSION", 0x3c62u},
    {"regHUBP2_DCHUBP_CNTL", 0x3c6bu},
    {"regHUBPREQ2_DCSURF_SURFACE_PITCH", 0x3c7fu},
    {"regHUBPREQ2_DCSURF_PRIMARY_SURFACE_ADDRESS", 0x3c82u},
    {"regHUBPREQ2_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH", 0x3c83u},
    {"regHUBPREQ2_DCSURF_SECONDARY_SURFACE_ADDRESS", 0x3c86u},
    {"regHUBPREQ2_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH", 0x3c87u},
    {"regHUBPREQ2_DCSURF_PRIMARY_META_SURFACE_ADDRESS", 0x3c8au},
    {"regHUBPREQ2_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH", 0x3c8bu},
    {"regHUBP3_DCSURF_SURFACE_CONFIG", 0x3d39u},
    {"regHUBP3_DCSURF_ADDR_CONFIG", 0x3d3au},
    {"regHUBP3_DCSURF_TILING_CONFIG", 0x3d3bu},
    {"regHUBP3_DCSURF_PRI_VIEWPORT_DIMENSION", 0x3d3eu},
    {"regHUBP3_DCHUBP_CNTL", 0x3d47u},
    {"regHUBPREQ3_DCSURF_SURFACE_PITCH", 0x3d5bu},
    {"regHUBPREQ3_DCSURF_PRIMARY_SURFACE_ADDRESS", 0x3d5eu},
    {"regHUBPREQ3_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH", 0x3d5fu},
    {"regHUBPREQ3_DCSURF_SECONDARY_SURFACE_ADDRESS", 0x3d62u},
    {"regHUBPREQ3_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH", 0x3d63u},
    {"regHUBPREQ3_DCSURF_PRIMARY_META_SURFACE_ADDRESS", 0x3d66u},
    {"regHUBPREQ3_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH", 0x3d67u},
};
#define PHX_SCANOUT_REG_COUNT (sizeof(phx_scanout_registers)/sizeof(phx_scanout_registers[0]))
#endif
