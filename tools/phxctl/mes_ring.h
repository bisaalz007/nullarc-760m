/* SPDX-License-Identifier: MIT
 * MES ring arithmetic shared by the actual transport and host tests.
 * Hardware pointers are monotonic uint32_t dword counters; one slot stays empty.
 */
#ifndef PHX_MES_RING_H
#define PHX_MES_RING_H
#include <stdint.h>
#include <stddef.h>
static inline int phxMesRoom(uint32_t wptr,uint32_t rptr,uint32_t ring,uint32_t need) {
    const uint32_t used=wptr-rptr;
    return ring && !(ring&(ring-1)) && need && used<ring && need<ring-used;
}
static inline int phxMesShape(size_t bytes,size_t status,size_t frameBytes,uint64_t seq) {
    return frameBytes && bytes==frameBytes && !(status&3) && status<=bytes &&
           bytes-status>=16 && seq!=UINT64_MAX;
}
static inline int phxMesCompleted(uint64_t wanted,uint64_t query,uint64_t command) {
    return wanted && query==wanted && command==wanted;
}
#endif
