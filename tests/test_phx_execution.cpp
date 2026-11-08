#include "phxbringup/PhxExecutionPolicy.h"
#include "phxbringup/PhxPspPolicy.h"
#include <cassert>
#include <cstdio>
#include <map>
int main() {
    PhxPspState psp;
    assert(psp.reusable() && !psp.confirmedTmrBytes);
    psp.setupResult(4096, true, 0);
    assert(psp.confirmedTmrBytes == 4096);
    psp.setupResult(8192, true, 0x100); // IOKit success is not PSP success.
    assert(!psp.confirmedTmrBytes);
    psp.setupResult(8192, false, 0);
    assert(!psp.confirmedTmrBytes);
    psp.completed(false); // command DMA may still be in flight
    assert(!psp.reusable());
    psp.completed(true); // a late observation cannot release the quarantine
    psp.setupResult(4096, true, 0);
    assert(!psp.reusable() && !psp.confirmedTmrBytes);
    psp.destroyed(false);
    assert(!psp.reusable());
    psp.destroyed(true);
    assert(psp.reusable() && !psp.confirmedTmrBytes);
    psp.setupResult(4096, true, 0);
    psp.completed(false);
    assert(!psp.confirmedTmrBytes);
    assert(phxCanonicalSpan(0x10000, 4096));
    assert(phxCanonicalSpan(0xffff800000000000ull, 4096));
    assert(!phxCanonicalSpan(0x7ffffffff000ull, 8192));
    assert(!phxCanonicalSpan(0xfffffffffffff000ull, 8192));
    assert(!phxCanonicalSpan(0x800000000000ull, 4096));
    assert(!phxCanonicalSpan(0x10000, 0));
    assert(!phxBufferSpan(~0ull - 7, 32, 4096));
    assert(phxBufferSpan(4096, 4096, 8192));
    assert(!phxVramSpan(4096,4096,4096,16384)); // A large BAR is not additional VRAM.
    assert(!phxVramSpan(4096,4096,16384,4096));
    assert(phxVramSpan(4096,4096,8192,8192));
    assert(phxQueueLayoutValid(0x1000,1024,0x2000,0x2020,24,0x10000,0x10000,0x1000));
    assert(!phxQueueLayoutValid(0x1000,1024,0x1ff8,0x2020,24,0x10000,0x10000,0x1000));
    assert(!phxQueueLayoutValid(0x1000,1024,0x2000,0x2018,24,0x10000,0x10000,0x1000));
    assert(!phxQueueLayoutValid(~0ull-255,1024,0x2000,0x2020,24,0x10000,0x10000,0x1000));
    assert(!phxQueueLayoutValid(1ull<<32,1024,0x2000,0x2020,24,1ull<<34,1ull<<34,0x1000));
    assert(!phxQueueLayoutValid(0x1000,1024,0x2000,0x2020,~0ull-7,0x10000,0x10000,0x1000));
    assert(!phxEngineAvailable(0, false, true));
    assert(!phxEngineAvailable(1, true, false));
    assert(phxEngineAvailable(1, true, true));
    assert(!phxMayRelease(false, 9, 10));
    assert(!phxMayRelease(true, 10, 10));
    assert(phxMayRelease(false, 10, 10));
    uint64_t mc=0, bytes=0, physical=0;
    assert(!phxDecodeMemoryLayout(0,0,0,mc,bytes,physical));
    assert(!phxDecodeMemoryLayout(0xffffffffu,1,1,mc,bytes,physical));
    assert(!phxDecodeMemoryLayout(2,1,1,mc,bytes,physical));
    assert(phxDecodeMemoryLayout(0x8000,0x817f,0x6a0,mc,bytes,physical));
    assert(mc==0x8000000000ull && bytes==(6ull<<30) && physical==0x6a0000000ull);
    uint64_t retired = 9;
    unsigned sleeps = 0;
    assert(!phxAwaitRetirement(10, 2, [&]() { return retired; }, []() { return false; }, [&]() { ++sleeps; }));
    assert(sleeps == 2);
    sleeps = 0;
    assert(phxAwaitRetirement(10, 2, [&]() { return retired; }, []() { return false; }, [&]() { retired = 10; ++sleeps; }));
    assert(sleeps == 1);
    assert(!phxAwaitRetirement(10, 2, [&]() { return retired; }, []() { return true; }, []() {}));
    // Exercise the exact map transaction used by PhxBringup, with injected
    // allocation/translation failures at every page and a pre-existing PTE.
    for (int fail = -1; fail < 4; ++fail) for (int kind = 0; kind < 3; ++kind) {
        std::map<uint64_t, uint64_t> entries;
        if (fail >= 0 && kind == 2) entries[0x10000 + fail * 4096] = 0x777;
        auto result = phxMapPages(0x10000, 0, 4 * 4096, 0x0000fffffffff000ull, 0x77,
            [fail, kind](uint64_t off, uint64_t &pa, uint64_t &len) {
                pa = kind == 0 && off / 4096 == static_cast<unsigned>(fail) ? 0 : 0x100000 + off;
                len = 4096;
            },
            [&entries, fail, kind](uint64_t va, bool alloc) -> uint64_t* {
                if (alloc && kind == 1 && va == 0x10000 + static_cast<uint64_t>(fail) * 4096) return nullptr;
                return &entries[va];
            }, [](uint64_t *) {});
        assert((result == PhxMapResult::Success) == (fail < 0));
        for (const auto &e : entries) {
            if (fail < 0) assert(e.second);
            else assert(e.second == (kind == 2 && e.first == 0x10000u + fail * 4096 ? 0x777u : 0));
        }
    }
    PhxUserFences<2> fences;
    assert(fences.record(0, 1, 8, 10));
    assert(fences.record(1, 2, 16, 20));
    assert(fences.available() == -1);
    assert(!fences.record(0, 3, 0, 30));
    unsigned writes = 0;
    fences.retire(9, [&](const PhxUserFence &) { ++writes; }); assert(writes == 0);
    fences.retire(10, [&](const PhxUserFence &f) { assert(f.handle == 1 && f.offset == 8 && f.seq == 10); ++writes; });
    assert(writes == 1 && fences.available() == 0);
    fences.retire(30, [&](const PhxUserFence &f) { assert(f.handle == 2); ++writes; });
    assert(writes == 2);
    fences.retire(30, [&](const PhxUserFence &) { ++writes; }); assert(writes == 2);
    puts("[PASS] real execution policies: rollback, engine routing, canonical spans, reclamation, multiple fences");
}
