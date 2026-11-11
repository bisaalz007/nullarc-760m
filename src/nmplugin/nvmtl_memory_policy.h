/* SPDX-License-Identifier: MIT */
#ifndef NVMTL_MEMORY_POLICY_H
#define NVMTL_MEMORY_POLICY_H
#include <stdint.h>

/* Engineering policy, not a hardware capability. Preserve existing defaults
 * unless the reserve consumes an integrated GPU's entire reported local heap.
 * Then reserve 1/16 of that heap. Explicit overrides remain unchanged. */
static inline uint64_t nvmtl_default_reserve(uint64_t legacy, uint64_t heap, int integrated)
{
    return integrated && heap && legacy >= heap ? heap / 16 : legacy;
}
static inline uint64_t nvmtl_working_set_limit(uint64_t room, uint64_t heap, int integrated)
{
    const uint64_t legacy_floor = UINT64_C(1) << 30;
    if (integrated && heap && heap < legacy_floor) return room < heap ? room : heap;
    return room > legacy_floor ? room : legacy_floor;
}
static inline uint64_t nvmtl_integrated_free(uint64_t heap, uint64_t budget, uint64_t used, uint64_t pending)
{
    const uint64_t capacity = budget < heap ? budget : heap;
    const uint64_t room = used < capacity ? capacity - used : 0;
    return pending < room ? room - pending : 0;
}
#endif
