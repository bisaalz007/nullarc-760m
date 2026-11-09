/* SPDX-License-Identifier: MIT
 * Read-only kernel-owned bootstrap allocation query. No caller-supplied ranges.
 * REFERENCE_COMPAT preserves the existing board policy; it is not HP ownership.
 */
#ifndef PHX_BOOTSTRAP_LAYOUT_H
#define PHX_BOOTSTRAP_LAYOUT_H
#include <stdint.h>
#define PHX_SEL_BOOTSTRAP_LAYOUT 33u
#define PHX_BOOTSTRAP_VERSION 1u
#define PHX_BOOTSTRAP_REFERENCE_COMPAT 1u
#define PHX_BOOTSTRAP_QUARANTINED 2u
#define PHX_BOOTSTRAP_HP_CAPTURED_PROFILE 4u
struct phx_bootstrap_layout {
    uint32_t version, flags;
    uint64_t ring_offset,ring_bytes,firmware_offset,firmware_bytes;
    uint64_t tmr_offset,tmr_bytes,mes_offset,mes_bytes;
    uint64_t fault_page_physical;
    uint64_t reserved[2];
};
static inline int phx_bootstrap_layout_valid(const struct phx_bootstrap_layout *p,uint64_t cap) {
    if (!p || p->version!=PHX_BOOTSTRAP_VERSION ||
        (p->flags!=PHX_BOOTSTRAP_REFERENCE_COMPAT && p->flags!=PHX_BOOTSTRAP_HP_CAPTURED_PROFILE) ||
        p->reserved[0] || p->reserved[1] || !p->fault_page_physical || (p->fault_page_physical&4095)) return 0;
    const uint64_t offsets[4]={p->ring_offset,p->firmware_offset,p->tmr_offset,p->mes_offset};
    const uint64_t sizes[4]={p->ring_bytes,p->firmware_bytes,p->tmr_bytes,p->mes_bytes};
    for (unsigned i=0;i<4;++i) {
        if (!sizes[i] || offsets[i]>cap || sizes[i]>cap-offsets[i]) return 0;
        for (unsigned j=0;j<i;++j) if(offsets[i]<offsets[j]+sizes[j] && offsets[j]<offsets[i]+sizes[i]) return 0;
    }
    return 1;
}
#endif
