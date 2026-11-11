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
/* Captured HP timing, read-only: sequoia-build39-display-timing.json.
 * Clock is nominal, derived from captured totals and the measured 60 Hz mode.
 * No display registers are programmed by this helper. */
#ifndef PHX_HP_DISPLAY_H
#define PHX_HP_DISPLAY_H
#include "phx_hp_memory.h"
#define PHX_HP_DISPLAY_REG_COUNT 14u
struct phx_hp_display_plan {
    uint32_t version, flags, width, height, pitch, refresh_millihz;
    uint32_t htotal, hsync_start, hsync_end, vtotal, vsync_start, vsync_end, sync_polarity, reserved;
    uint64_t aperture_physical, backing_physical, scanout_mc, scanout_offset, scanout_bytes, nominal_pixel_clock_hz;
};
static_assert(sizeof(phx_hp_display_plan)==104,"display plan layout");
static const struct phx_scanout_register phx_hp_display_registers[]={
    {"regOTG0_OTG_H_TOTAL",0x4feau},
    {"regOTG0_OTG_H_BLANK_START_END",0x4febu},
    {"regOTG0_OTG_H_SYNC_A",0x4fecu},
    {"regOTG0_OTG_H_SYNC_A_CNTL",0x4fedu},
    {"regOTG0_OTG_V_TOTAL",0x4fefu},
    {"regOTG0_OTG_V_TOTAL_MIN",0x4ff0u},
    {"regOTG0_OTG_V_TOTAL_MAX",0x4ff1u},
    {"regOTG0_OTG_V_TOTAL_CONTROL",0x4ff3u},
    {"regOTG0_OTG_V_BLANK_START_END",0x4ff6u},
    {"regOTG0_OTG_V_SYNC_A",0x4ff7u},
    {"regOTG0_OTG_V_SYNC_A_CNTL",0x4ff8u},
    {"regOTG0_OTG_CONTROL",0x5001u},
    {"regOTG0_OTG_INTERLACE_CONTROL",0x5004u},
    {"regOTG0_OTG_STATUS_FRAME_COUNT",0x500cu},
};
struct PhxDisplayExpected { uint32_t value,mask; };
static const PhxDisplayExpected phx_hp_display_expected[]={
    {0x8d3u,0x7fffu}, // regOTG0_OTG_H_TOTAL
    {0x12408a4u,0x7fff7fffu}, // regOTG0_OTG_H_BLANK_START_END
    {0x200000u,0x7fff7fffu}, // regOTG0_OTG_H_SYNC_A
    {0x0u,0x1u}, // regOTG0_OTG_H_SYNC_A_CNTL
    {0x4d7u,0x7fffu}, // regOTG0_OTG_V_TOTAL
    {0x0u,0x7fffu}, // regOTG0_OTG_V_TOTAL_MIN
    {0x0u,0x7fffu}, // regOTG0_OTG_V_TOTAL_MAX
    {0x0u,0xffffffffu}, // regOTG0_OTG_V_TOTAL_CONTROL
    {0x2504d5u,0x7fff7fffu}, // regOTG0_OTG_V_BLANK_START_END
    {0x60000u,0x7fff7fffu}, // regOTG0_OTG_V_SYNC_A
    {0x1u,0x1u}, // regOTG0_OTG_V_SYNC_A_CNTL
    {0x11201u,0x1u}, // regOTG0_OTG_CONTROL
    {0x0u,0x1u}, // regOTG0_OTG_INTERLACE_CONTROL
    {0x146a0u,0x0u}, // regOTG0_OTG_STATUS_FRAME_COUNT
};
static inline bool phxHpDisplayPlan(const phx_memory_layout &memory,const PhxVbiosInfo &firmware,
        const uint32_t *reservation_a,const uint32_t *reservation_b,const uint32_t *timing_a,const uint32_t *timing_b,
        uint64_t width,uint64_t height,uint64_t pitch,uint64_t depth,phx_hp_display_plan &out) {
    out={};
    if (!timing_a || !timing_b || width!=1920 || height!=1200 || pitch!=7680 || depth!=32 ||
        !phxHpMemoryMatches(memory,firmware,reservation_a,reservation_b)) return false;
    for (unsigned i=0;i<PHX_HP_DISPLAY_REG_COUNT;++i) {
        const auto &e=phx_hp_display_expected[i];
        if (((timing_a[i]^e.value)&e.mask) || ((timing_b[i]^e.value)&e.mask)) return false;
    }
    out.version=1;out.flags=3; // captured configuration + nominal (not directly measured) clock
    out.width=1920;out.height=1200;out.pitch=7680;out.refresh_millihz=60000;
    out.htotal=2260;out.hsync_start=1968;out.hsync_end=2000;
    out.vtotal=1240;out.vsync_start=1203;out.vsync_end=1209;out.sync_polarity=1;
    out.aperture_physical=memory.cpu_aperture_base;out.backing_physical=memory.physical_base;
    out.scanout_mc=memory.mc_base;out.scanout_offset=0;out.scanout_bytes=(uint64_t)out.pitch*out.height;
    out.nominal_pixel_clock_hz=(uint64_t)out.htotal*out.vtotal*out.refresh_millihz/1000;
    return out.scanout_bytes<=memory.cpu_aperture_bytes && out.scanout_bytes<=phx_hp_console_exclusion;
}
#endif
