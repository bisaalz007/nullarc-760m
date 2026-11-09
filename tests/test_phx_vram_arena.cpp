#include "amd/phx_vram_arena.h"
#include "amd/phx_hp_memory.h"
#include <fstream>
#include <string>
#include "amd/phx_bootstrap_layout.h"
#include "../tools/phxctl/mes_ring.h"
#include <cassert>
#include <cstdio>
#include <random>
#include <vector>
int main() {
    std::ifstream capture("tests/fixtures/hp-760m-reservations.hex");unsigned count=0;capture>>count;
    assert(capture && count==PHX_RESERVATION_REG_COUNT);
    uint32_t samples[2][PHX_RESERVATION_REG_COUNT];
    for (auto &sample:samples) for (auto &value:sample) capture>>std::hex>>value;
    assert(capture.good());
    std::ifstream romfile("tests/fixtures/hp-760m-atom-metadata.hex");size_t total=0,off=0;std::string hex;
    romfile>>total;std::vector<uint8_t> rom(total);
    while (romfile>>off>>hex) for (size_t i=0;i<hex.size()/2;++i) rom[off+i]=(uint8_t)std::stoul(hex.substr(2*i,2),nullptr,16);
    PhxVbiosInfo info{};assert(phxDecodeAtom(rom.data(),rom.size(),info)==PhxVbiosResult::Decoded);
    phx_memory_layout memory{};memory.version=1;memory.flags=3;memory.raw_base=0x8000;memory.raw_top=0x801f;memory.raw_offset=0x260;
    memory.mc_base=0x8000000000ull;memory.physical_base=0x260000000ull;memory.vram_bytes=512ull<<20;
    memory.cpu_aperture_base=0x2b0000000ull;memory.cpu_aperture_bytes=256ull<<20;
    assert(phxHpMemoryMatches(memory,info,samples[0],samples[1]));
    for (unsigned i=0;i<count;++i) if (phx_hp_memory_expected[i].mask) {
        const uint32_t bit=phx_hp_memory_expected[i].mask&(~phx_hp_memory_expected[i].mask+1);
        samples[1][i]^=bit;assert(!phxHpMemoryMatches(memory,info,samples[0],samples[1]));samples[1][i]^=bit;
    }
    info.extraDecoded=false;assert(!phxHpMemoryMatches(memory,info,samples[0],samples[1]));
    info.extraDecoded=true;memory.cpu_aperture_base+=0x10000000;
    assert(phxHpMemoryMatches(memory,info,samples[0],samples[1])); // PCI-assigned CPU BAR may move; MC backing cannot.
    memory.physical_base+=0x1000000;assert(!phxHpMemoryMatches(memory,info,samples[0],samples[1]));
    PhxVramArena<32> a;PhxVramLease x,mes,ring,fw,tmr;
    assert(!a.allocate(4096,4096,x));
    assert(a.begin(256ull<<20) && !a.begin(1));
    assert(a.exclude(0,16ull<<20));
    assert(!a.exclude(UINT64_MAX,4096));
    assert(a.seal() && !a.exclude(0,1));
    assert(a.allocateAt(32ull<<20,8ull<<20,mes));
    assert(a.allocateAt(0x1100000,0x9000,ring));
    assert(a.allocateAt(64ull<<20,16ull<<20,fw));
    assert(!a.allocateAt(mes.offset+4096,4096,x));
    // Measured HP Linux requirement (64 MiB): cannot overlap staging or MES.
    assert(a.allocate(64ull<<20,64ull<<20,tmr));
    assert(tmr.offset==(128ull<<20));
    assert(!a.contains(tmr,tmr.offset+tmr.bytes-4,8));
    auto stale=tmr;assert(a.release(tmr));
    assert(a.allocate(64ull<<20,64ull<<20,tmr));
    assert(!a.contains(stale,stale.offset,4) && !a.release(stale));
    assert(a.pin(tmr) && !a.release(tmr));
    a.quarantine();assert(!a.allocate(1,1,x) && !a.release(fw) && !a.begin(256ull<<20));
    PhxVramArena<2> small;assert(small.begin(UINT64_MAX) && small.seal());
    assert(small.allocateAt(UINT64_MAX-4095,4095,x));
    assert(!small.allocate(4096,3,tmr));
    assert(small.allocateAt(0,4096,tmr));assert(!small.allocate(4096,4096,fw));
    // Deterministic allocation/free stress checks every returned interval against
    // live leases; exercise fragmentation, alignment, capacity and stale handles.
    PhxVramArena<32> stress;assert(stress.begin(1ull<<20) && stress.exclude(0,4096) && stress.seal());
    std::mt19937 rng(760);std::vector<PhxVramLease> live;
    for (unsigned i=0;i<10000;++i) {
        if (!live.empty() && rng()%3==0) {
            const auto pos=rng()%live.size();assert(stress.release(live[pos]));live.erase(live.begin()+pos);
        } else {
            const uint64_t align=1ull<<(12+rng()%5),bytes=4096*(1+rng()%32);
            PhxVramLease lease;
            if (stress.allocate(bytes,align,lease)) {
                assert(!(lease.offset&(align-1)) && lease.offset>=4096 && lease.offset+bytes<=1ull<<20);
                for (const auto &other:live) assert(lease.offset>=other.offset+other.bytes || other.offset>=lease.offset+lease.bytes);
                live.push_back(lease);
            }
        }
    }
    phx_bootstrap_layout p{};p.version=1;p.flags=1;p.ring_offset=0x1100000;p.ring_bytes=0x9000;
    p.firmware_offset=0x4000000;p.firmware_bytes=0x1000000;p.tmr_offset=0x8000000;p.tmr_bytes=0x4000000;
    p.mes_offset=0x2000000;p.mes_bytes=0x800000;p.fault_page_physical=0x100000;
    assert(sizeof(p)==96 && phx_bootstrap_layout_valid(&p,256ull<<20));
    p.tmr_offset=p.mes_offset;assert(!phx_bootstrap_layout_valid(&p,256ull<<20));
    assert(phxMesRoom(0,0,1024,128));assert(phxMesRoom(0xfffffff0u,0xffffff00u,1024,128));
    assert(phxMesRoom(64,0xffffffc0u,1024,128));
    assert(!phxMesRoom(1024,0,1024,1) && !phxMesRoom(900,0,1024,128));
    assert(!phxMesRoom(0,1,1024,128));
    assert(phxMesShape(256,240,256,0));assert(!phxMesShape(256,244,256,0));
    assert(!phxMesShape(255,240,256,0) && !phxMesShape(256,240,256,UINT64_MAX));
    assert(phxMesCompleted(0x100000001ull,0x100000001ull,0x100000001ull));
    assert(!phxMesCompleted(1,0x100000001ull,1) && !phxMesCompleted(2,2,1));
    puts("[PASS] exclusive leases, stale handles, 64-MiB TMR, quarantine, randomized fragmentation, MES capacity and 64-bit fences");
}
