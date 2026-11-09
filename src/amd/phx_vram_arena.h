/* SPDX-License-Identifier: MIT
 * Exclusive interval allocator for a driver-owned VRAM pool. The caller must
 * establish ownership and add firmware/display exclusions before sealing it.
 * Addressable/zero VRAM is not ownership evidence. Caller serializes access.
 */
#ifndef PHX_VRAM_ARENA_H
#define PHX_VRAM_ARENA_H
#include <stdint.h>
struct PhxVramLease { uint64_t id{0}, offset{0}, bytes{0}; };
template<unsigned Capacity> class PhxVramArena {
    struct Entry { PhxVramLease lease{}; bool excluded{false}, pinned{false}; } entries[Capacity]{};
    uint64_t limit{0}, nextId{0};
    bool sealed{false}, lost{false};
    static bool span(uint64_t off,uint64_t bytes,uint64_t cap) {
        return bytes && off<=cap && bytes<=cap-off;
    }
    static bool overlap(uint64_t a,uint64_t an,uint64_t b,uint64_t bn) {
        return a<b+bn && b<a+an; // callers validated both spans
    }
    Entry *find(uint64_t id) {
        if (id) for (auto &e:entries) if (e.lease.id==id) return &e;
        return nullptr;
    }
    bool insert(uint64_t off,uint64_t bytes,bool excluded,PhxVramLease &out) {
        if (nextId==UINT64_MAX) return false; // never recycle a stale lease identity
        for (auto &e:entries) if (!e.lease.id) {
            e.lease={++nextId,off,bytes}; e.excluded=excluded; e.pinned=false;out=e.lease;return true;
        }
        return false;
    }
public:
    bool begin(uint64_t bytes) {
        if (!bytes || limit || lost) return false;
        limit=bytes;return true;
    }
    bool exclude(uint64_t off,uint64_t bytes) {
        if (!limit || sealed || lost || !span(off,bytes,limit)) return false;
        PhxVramLease ignored;return insert(off,bytes,true,ignored);
    }
    bool seal() { if (!limit || sealed || lost) return false;sealed=true;return true; }
    bool ready() const { return sealed && !lost; }
    bool allocateAt(uint64_t off,uint64_t bytes,PhxVramLease &out) {
        out={};
        if (!ready() || !span(off,bytes,limit)) return false;
        for (const auto &e:entries) if (e.lease.id && overlap(off,bytes,e.lease.offset,e.lease.bytes)) return false;
        return insert(off,bytes,false,out);
    }
    bool allocate(uint64_t bytes,uint64_t align,PhxVramLease &out) {
        out={};
        if (!ready() || !bytes || !align || (align&(align-1)) || bytes>limit) return false;
        uint64_t off=0;
        for (unsigned n=0;n<=Capacity;++n) {
            if (off>UINT64_MAX-(align-1)) return false;
            off=(off+align-1)&~(align-1);
            if (!span(off,bytes,limit)) return false;
            bool hit=false;
            for (const auto &e:entries) if (e.lease.id && overlap(off,bytes,e.lease.offset,e.lease.bytes)) {
                off=e.lease.offset+e.lease.bytes;hit=true;break;
            }
            if (!hit) return insert(off,bytes,false,out);
        }
        return false;
    }
    bool contains(const PhxVramLease &lease,uint64_t off,uint64_t bytes) const {
        if (!ready() || off<lease.offset || !span(off-lease.offset,bytes,lease.bytes)) return false;
        for (const auto &e:entries) if (!e.excluded && e.lease.id==lease.id &&
            e.lease.offset==lease.offset && e.lease.bytes==lease.bytes) return true;
        return false;
    }
    bool pin(const PhxVramLease &lease) {
        auto *e=find(lease.id);
        if (!contains(lease,lease.offset,lease.bytes) || !e) return false;
        e->pinned=true;return true;
    }
    bool release(const PhxVramLease &lease) {
        auto *e=find(lease.id);
        if (!e || e->pinned || !contains(lease,lease.offset,lease.bytes)) return false;
        *e={};return true;
    }
    void quarantine() { lost=true; } // DMA lifetime unknown: no reuse, reset or release
};
#endif
