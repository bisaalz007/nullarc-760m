/* SPDX-License-Identifier: MIT
 * Pure policies shared by real kernel execution and host failure-injection tests.
 * No register values or simulated command retirement.
 */
#ifndef PHX_EXECUTION_POLICY_H
#define PHX_EXECUTION_POLICY_H
#include <stdint.h>
#include "../amd/phx_memory_layout.h"

static inline bool phxCanonicalSpan(uint64_t address, uint64_t bytes) {
    if (!bytes) return false;
    const uint64_t top = address >> 47;
    if (top != 0 && top != 0x1ffff) return false;
    const uint64_t va = address & ((1ull << 48) - 1);
    if (va < 0x10000) return false;
    const uint64_t end = top ? (1ull << 48) : (1ull << 47);
    return bytes <= end - va;
}
static inline bool phxBufferSpan(uint64_t offset, uint64_t bytes, uint64_t capacity) {
    return bytes && offset <= capacity && bytes <= capacity - offset;
}
static inline bool phxVramSpan(uint64_t offset, uint64_t bytes, uint64_t vram, uint64_t aperture) {
    return phxBufferSpan(offset, bytes, vram) && phxBufferSpan(offset, bytes, aperture);
}
static inline bool phxQueueLayoutValid(uint64_t ring, uint64_t dwords, uint64_t wb, uint64_t fence,
                                       uint64_t doorbell, uint64_t vram, uint64_t aperture, uint64_t doorbellBytes) {
    if (dwords < 256 || dwords > 65536 || (dwords & (dwords - 1)) || (ring & 255) ||
        (wb & 7) || (fence & 7) || (doorbell & 7)) return false;
    const uint64_t bytes = dwords * 4;
    // Queue offsets are stored as uint32_t; reject truncation as well as span overflow.
    if (!phxVramSpan(ring, bytes, vram, aperture) || !phxBufferSpan(ring, bytes, 1ull << 32) ||
        !phxVramSpan(wb, 32, vram, aperture) || !phxBufferSpan(wb, 32, 1ull << 32) ||
        !phxVramSpan(fence, 8, vram, aperture) || !phxBufferSpan(fence, 8, 1ull << 32) ||
        !phxBufferSpan(doorbell, 8, doorbellBytes)) return false;
    return !(ring < wb + 32 && wb < ring + bytes) &&
           !(ring < fence + 8 && fence < ring + bytes) &&
           !(wb < fence + 8 && fence < wb + 32);
}
static inline bool phxEngineAvailable(uint32_t ip, bool graphics, bool compute) {
    return (ip == 0 && graphics) || (ip == 1 && compute);
}
static inline bool phxMayRelease(bool lost, uint64_t retired, uint64_t submitted) {
    return !lost && retired >= submitted;
}

/* Existing MMHUB FB location encoding: 24-bit BASE/TOP in 16 MiB units,
 * OFFSET in the same units. Zeroed/unreadable banks are not a memory size. */
static inline bool phxDecodeMemoryLayout(uint32_t base, uint32_t top, uint32_t offset,
                                        uint64_t &mc, uint64_t &bytes, uint64_t &physical) {
    return phx_memory_decode_raw(base, top, offset, &mc, &bytes, &physical);
}

enum class PhxMapResult { Success, PhysicalPage, PageTable, Occupied };
/* Caller serializes page tables. On any failure, clear exactly the PTEs this
 * operation installed. Existing mappings and allocated directory pages survive.
 * Caller must invalidate a bound hardware VMID after success OR rollback.
 */
template<class Physical, class Lookup, class Flush>
PhxMapResult phxMapPages(uint64_t va, uint64_t offset, uint64_t bytes,
                        uint64_t addressMask, uint64_t flags,
                        Physical physical, Lookup lookup, Flush flush) {
    uint64_t done = 0;
    PhxMapResult result = PhxMapResult::Success;
    for (; done < bytes; done += 4096) {
        uint64_t pa = 0, contiguous = 0;
        physical(offset + done, pa, contiguous);
        if (!pa || (pa & ~addressMask) || contiguous < 4096) {
            result = PhxMapResult::PhysicalPage; break;
        }
        uint64_t *pte = lookup(va + done, true);
        if (!pte) { result = PhxMapResult::PageTable; break; }
        if (*pte) { result = PhxMapResult::Occupied; break; }
        *pte = pa | flags;
        flush(pte);
    }
    if (result != PhxMapResult::Success) {
        for (uint64_t p = 0; p < done; p += 4096) {
            uint64_t *pte = lookup(va + p, false);
            if (pte) { *pte = 0; flush(pte); }
        }
    }
    return result;
}
template<class Retired, class Lost, class Pause>
[[nodiscard]] bool phxAwaitRetirement(uint64_t submitted, unsigned attempts,
                                    Retired retired, Lost lost, Pause pause) {
    for (unsigned i = 0; i < attempts; ++i) {
        if (lost()) return false;
        if (retired() >= submitted) return true;
        pause();
    }
    return phxMayRelease(lost(), retired(), submitted);
}

struct PhxUserFence { uint32_t handle, offset; uint64_t seq; };
template<unsigned Count> class PhxUserFences {
    PhxUserFence slots[Count]{};
public:
    int available() const {
        for (unsigned i = 0; i < Count; ++i) if (!slots[i].seq) return static_cast<int>(i);
        return -1;
    }
    bool record(unsigned slot, uint32_t handle, uint32_t offset, uint64_t seq) {
        if (slot >= Count || slots[slot].seq || !seq) return false;
        slots[slot] = PhxUserFence{handle, offset, seq}; return true;
    }
    template<class Write> void retire(uint64_t through, Write write) {
        for (auto &f : slots) if (f.seq && f.seq <= through) { write(f); f = PhxUserFence{}; }
    }
};
#endif
