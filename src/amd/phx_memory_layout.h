/* SPDX-License-Identifier: MIT
 * Read-only MMHUB/BAR snapshot. Decoding addresses does not reserve memory,
 * establish CPU-window placement or authorize firmware/queue initialization.
 */
#ifndef PHX_MEMORY_LAYOUT_H
#define PHX_MEMORY_LAYOUT_H
#include <stdint.h>
#define PHX_SEL_MEMORY_LAYOUT 31u
#define PHX_MEMORY_LAYOUT_VERSION 1u
#define PHX_MEMORY_DECODED 1u
#define PHX_MEMORY_DIAGNOSTIC_ONLY 2u
#define PHX_MEMORY_DEVICE_LOST 4u
struct phx_memory_layout {
    uint32_t version, flags;
    uint32_t raw_base, raw_top, raw_offset, reserved0;
    uint64_t mc_base, physical_base, vram_bytes;
    uint64_t cpu_aperture_base, cpu_aperture_bytes;
    uint64_t reserved[2];
};

/* Existing MMHUB encoding, shared with the actual kernel decoder. */
static inline int phx_memory_decode_raw(uint32_t base, uint32_t top, uint32_t offset,
    uint64_t *mc, uint64_t *bytes, uint64_t *physical) {
    if (base == UINT32_MAX || top == UINT32_MAX || offset == UINT32_MAX ||
        !(base | top | offset)) return 0;
    base &= 0xffffffu; top &= 0xffffffu;
    if (top < base || !offset) return 0;
    *mc = (uint64_t)base << 24;
    *bytes = ((uint64_t)(top - base) + 1) << 24;
    *physical = (uint64_t)offset << 24;
    return 1;
}
static inline int phx_memory_layout_valid(const struct phx_memory_layout *p) {
    uint64_t mc, bytes, physical;
    if (!p || p->version != PHX_MEMORY_LAYOUT_VERSION || !(p->flags & PHX_MEMORY_DECODED) ||
        (p->flags & ~(PHX_MEMORY_DECODED | PHX_MEMORY_DIAGNOSTIC_ONLY | PHX_MEMORY_DEVICE_LOST)) ||
        p->reserved0 || p->reserved[0] || p->reserved[1] ||
        !phx_memory_decode_raw(p->raw_base, p->raw_top, p->raw_offset, &mc, &bytes, &physical)) return 0;
    return p->mc_base == mc && p->physical_base == physical && p->vram_bytes == bytes &&
        bytes <= UINT64_MAX - mc && bytes <= UINT64_MAX - physical &&
        ((!p->cpu_aperture_base && !p->cpu_aperture_bytes) ||
         (p->cpu_aperture_base && p->cpu_aperture_bytes &&
          !(p->cpu_aperture_base & 4095) && !(p->cpu_aperture_bytes & 4095) &&
          p->cpu_aperture_bytes <= UINT64_MAX - p->cpu_aperture_base));
}
/* Addresses only. Never an ownership or GPU-access permission check. */
static inline int phx_memory_translate(const struct phx_memory_layout *p,
    uint64_t offset, uint64_t bytes, uint64_t *mc, uint64_t *physical) {
    if (!mc || !physical || !phx_memory_layout_valid(p) || !bytes ||
        offset > p->vram_bytes || bytes > p->vram_bytes - offset) return 0;
    *mc = p->mc_base + offset;
    *physical = p->physical_base + offset;
    return 1;
}
#endif
