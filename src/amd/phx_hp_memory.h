/* SPDX-License-Identifier: MIT
 * Exact measured HP firmware-display reservation configuration, not CU-derived.
 * Source: hardware/dumps/hp_envy_760m/sequoia-build37-reservations.json.
 * HUBP status is ignored; DMCUB_CNTL compares only its documented enable bit.
 * Register definitions: Linux v6.14 dcn_3_1_4_offset.h / _sh_mask.h.
 * A matching snapshot is a platform constraint, not proof of GPU execution.
 */
#ifndef PHX_HP_MEMORY_H
#define PHX_HP_MEMORY_H
#include "phx_reservation_regs.h"
#include "phx_memory_layout.h"
#include "phx_vbios.h"
struct PhxHpMemoryExpected { uint32_t value,mask; };
static const PhxHpMemoryExpected phx_hp_memory_expected[]={
    {0x8u,0xffffffffu}, // regHUBP0_DCSURF_SURFACE_CONFIG
    {0x0u,0xffffffffu}, // regHUBP0_DCSURF_ADDR_CONFIG
    {0x80u,0xffffffffu}, // regHUBP0_DCSURF_TILING_CONFIG
    {0x4b00780u,0xffffffffu}, // regHUBP0_DCSURF_PRI_VIEWPORT_DIMENSION
    {0x0u,0x0u}, // regHUBP0_DCHUBP_CNTL
    {0x77fu,0xffffffffu}, // regHUBPREQ0_DCSURF_SURFACE_PITCH
    {0x0u,0xffffffffu}, // regHUBPREQ0_DCSURF_PRIMARY_SURFACE_ADDRESS
    {0x80u,0xffffffffu}, // regHUBPREQ0_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ0_DCSURF_SECONDARY_SURFACE_ADDRESS
    {0x80u,0xffffffffu}, // regHUBPREQ0_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ0_DCSURF_PRIMARY_META_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ0_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH
    {0x8u,0xffffffffu}, // regHUBP1_DCSURF_SURFACE_CONFIG
    {0x0u,0xffffffffu}, // regHUBP1_DCSURF_ADDR_CONFIG
    {0x80u,0xffffffffu}, // regHUBP1_DCSURF_TILING_CONFIG
    {0x0u,0xffffffffu}, // regHUBP1_DCSURF_PRI_VIEWPORT_DIMENSION
    {0x0u,0x0u}, // regHUBP1_DCHUBP_CNTL
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_SURFACE_PITCH
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_PRIMARY_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_SECONDARY_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_PRIMARY_META_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ1_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH
    {0x8u,0xffffffffu}, // regHUBP2_DCSURF_SURFACE_CONFIG
    {0x0u,0xffffffffu}, // regHUBP2_DCSURF_ADDR_CONFIG
    {0x80u,0xffffffffu}, // regHUBP2_DCSURF_TILING_CONFIG
    {0x0u,0xffffffffu}, // regHUBP2_DCSURF_PRI_VIEWPORT_DIMENSION
    {0x0u,0x0u}, // regHUBP2_DCHUBP_CNTL
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_SURFACE_PITCH
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_PRIMARY_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_SECONDARY_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_PRIMARY_META_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ2_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH
    {0x8u,0xffffffffu}, // regHUBP3_DCSURF_SURFACE_CONFIG
    {0x0u,0xffffffffu}, // regHUBP3_DCSURF_ADDR_CONFIG
    {0x80u,0xffffffffu}, // regHUBP3_DCSURF_TILING_CONFIG
    {0x0u,0xffffffffu}, // regHUBP3_DCSURF_PRI_VIEWPORT_DIMENSION
    {0x0u,0x0u}, // regHUBP3_DCHUBP_CNTL
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_SURFACE_PITCH
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_PRIMARY_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_PRIMARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_SECONDARY_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_SECONDARY_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_PRIMARY_META_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regHUBPREQ3_DCSURF_PRIMARY_META_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION0_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION0_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION1_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION1_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION2_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION2_OFFSET_HIGH
    {0x1fe00000u,0xffffffffu}, // regDMCUB_REGION4_OFFSET
    {0x80u,0xffffffffu}, // regDMCUB_REGION4_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION5_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION5_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION6_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION6_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION7_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION7_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION0_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION1_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION2_TOP_ADDRESS
    {0x8000ffffu,0xffffffffu}, // regDMCUB_REGION4_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION5_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION6_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION7_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW0_BASE_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW1_BASE_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW2_BASE_ADDRESS
    {0x3000000u,0xffffffffu}, // regDMCUB_REGION3_CW3_BASE_ADDRESS
    {0x4000000u,0xffffffffu}, // regDMCUB_REGION3_CW4_BASE_ADDRESS
    {0x5000000u,0xffffffffu}, // regDMCUB_REGION3_CW5_BASE_ADDRESS
    {0x6000000u,0xffffffffu}, // regDMCUB_REGION3_CW6_BASE_ADDRESS
    {0x7000000u,0xffffffffu}, // regDMCUB_REGION3_CW7_BASE_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW0_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW1_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW2_TOP_ADDRESS
    {0x8301ffffu,0xffffffffu}, // regDMCUB_REGION3_CW3_TOP_ADDRESS
    {0x8400ffffu,0xffffffffu}, // regDMCUB_REGION3_CW4_TOP_ADDRESS
    {0x8500ffffu,0xffffffffu}, // regDMCUB_REGION3_CW5_TOP_ADDRESS
    {0x8600ffffu,0xffffffffu}, // regDMCUB_REGION3_CW6_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW7_TOP_ADDRESS
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW0_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW0_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW1_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW1_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW2_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW2_OFFSET_HIGH
    {0x1fe20000u,0xffffffffu}, // regDMCUB_REGION3_CW3_OFFSET
    {0x80u,0xffffffffu}, // regDMCUB_REGION3_CW3_OFFSET_HIGH
    {0x1fe40000u,0xffffffffu}, // regDMCUB_REGION3_CW4_OFFSET
    {0x80u,0xffffffffu}, // regDMCUB_REGION3_CW4_OFFSET_HIGH
    {0x1fe50000u,0xffffffffu}, // regDMCUB_REGION3_CW5_OFFSET
    {0x80u,0xffffffffu}, // regDMCUB_REGION3_CW5_OFFSET_HIGH
    {0x1fe60000u,0xffffffffu}, // regDMCUB_REGION3_CW6_OFFSET
    {0x80u,0xffffffffu}, // regDMCUB_REGION3_CW6_OFFSET_HIGH
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW7_OFFSET
    {0x0u,0xffffffffu}, // regDMCUB_REGION3_CW7_OFFSET_HIGH
    {0x10000u,0x10000u}, // regDMCUB_CNTL
    {0x0u,0xffffffffu}, // regDMCUB_CNTL2
    {0x8000u,0xffffffffu}, // regDCN_VM_FB_LOCATION_BASE
    {0x260u,0xffffffffu}, // regDCN_VM_FB_OFFSET
    {0x1000000u,0xffffffffu}, // regCURSOR0_0_CURSOR_CONTROL
    {0x0u,0xffffffffu}, // regCURSOR0_0_CURSOR_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regCURSOR0_0_CURSOR_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regCURSOR0_0_CURSOR_SIZE
    {0x1000000u,0xffffffffu}, // regCURSOR0_1_CURSOR_CONTROL
    {0x0u,0xffffffffu}, // regCURSOR0_1_CURSOR_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regCURSOR0_1_CURSOR_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regCURSOR0_1_CURSOR_SIZE
    {0x1000000u,0xffffffffu}, // regCURSOR0_2_CURSOR_CONTROL
    {0x0u,0xffffffffu}, // regCURSOR0_2_CURSOR_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regCURSOR0_2_CURSOR_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regCURSOR0_2_CURSOR_SIZE
    {0x1000000u,0xffffffffu}, // regCURSOR0_3_CURSOR_CONTROL
    {0x0u,0xffffffffu}, // regCURSOR0_3_CURSOR_SURFACE_ADDRESS
    {0x0u,0xffffffffu}, // regCURSOR0_3_CURSOR_SURFACE_ADDRESS_HIGH
    {0x0u,0xffffffffu}, // regCURSOR0_3_CURSOR_SIZE
    {0x0u,0xffffffffu}, // regHUBP0_DCSURF_PRI_VIEWPORT_START
    {0x0u,0xffffffffu}, // regHUBP1_DCSURF_PRI_VIEWPORT_START
    {0x0u,0xffffffffu}, // regHUBP2_DCSURF_PRI_VIEWPORT_START
    {0x0u,0xffffffffu}, // regHUBP3_DCSURF_PRI_VIEWPORT_START
};
// Allocation policy: round the measured 9,216,000-byte linear console prefix
// up to 16 MiB. This is conservative protection, not a hardware size claim.
static const uint64_t phx_hp_console_exclusion=16ull<<20;
static inline bool phxHpMemoryMatches(const phx_memory_layout &m,const PhxVbiosInfo &f,
                                     const uint32_t *first,const uint32_t *second) {
    if (!phx_memory_layout_valid(&m) || !first || !second ||
        m.mc_base!=0x8000000000ull || m.physical_base!=0x260000000ull ||
        m.vram_bytes!=(512ull<<20) || m.cpu_aperture_bytes!=(256ull<<20) ||
        f.romFormat!=2 || f.romContent!=3 || f.masterFormat!=2 || f.masterContent!=1 ||
        f.firmwareFormat!=3 || f.firmwareContent!=4 || f.firmwareRevision!=0x160c001bu ||
        !f.usageDecoded || f.usageFormat!=2 || f.usageContent!=1 || f.firmwareStartRawKiB ||
        f.firmwareUsageBytes || f.driverUsageBytes || !f.extraDecoded || f.extraFirmwareBytes!=(2ull<<20)) return false;
    for (unsigned i=0;i<PHX_RESERVATION_REG_COUNT;++i)
        if ((first[i]&phx_hp_memory_expected[i].mask)!=phx_hp_memory_expected[i].value ||
            (second[i]&phx_hp_memory_expected[i].mask)!=phx_hp_memory_expected[i].value) return false;
    return true;
}
#endif
