#include "amd/phx_hp_display.h"
#include <fstream>
#include <string>
#include <vector>
#include <cassert>
#include <cstdio>
int main() {
    std::ifstream reservations("tests/fixtures/hp-760m-reservations.hex");unsigned count=0;reservations>>count;
    assert(count==PHX_RESERVATION_REG_COUNT);
    uint32_t r[2][PHX_RESERVATION_REG_COUNT];
    for (auto &sample:r) for (auto &v:sample) reservations>>std::hex>>v;
    assert(reservations.good());
    std::ifstream timing("tests/fixtures/hp-760m-display.hex");timing>>count;assert(count==PHX_HP_DISPLAY_REG_COUNT);
    uint32_t t[2][PHX_HP_DISPLAY_REG_COUNT];
    for (auto &sample:t) for (auto &v:sample) timing>>std::hex>>v;
    assert(timing.good());
    std::ifstream romfile("tests/fixtures/hp-760m-atom-metadata.hex");size_t total=0,off=0;std::string hex;
    romfile>>total;std::vector<uint8_t> rom(total);
    while (romfile>>off>>hex) for (size_t i=0;i<hex.size()/2;++i) rom[off+i]=(uint8_t)std::stoul(hex.substr(2*i,2),nullptr,16);
    PhxVbiosInfo info{};assert(phxDecodeAtom(rom.data(),rom.size(),info)==PhxVbiosResult::Decoded);
    phx_memory_layout m{};m.version=1;m.flags=3;m.raw_base=0x8000;m.raw_top=0x801f;m.raw_offset=0x260;
    m.mc_base=0x8000000000ull;m.physical_base=0x260000000ull;m.vram_bytes=512ull<<20;
    m.cpu_aperture_base=0x2b0000000ull;m.cpu_aperture_bytes=256ull<<20;
    phx_hp_display_plan p{};
    auto valid=[&](uint64_t w=1920,uint64_t h=1200,uint64_t pitch=7680,uint64_t depth=32) {
        return phxHpDisplayPlan(m,info,r[0],r[1],t[0],t[1],w,h,pitch,depth,p);
    };
    assert(valid());assert(p.htotal==2260 && p.vtotal==1240 && p.nominal_pixel_clock_hz==168144000);
    assert(p.hsync_start==1968 && p.hsync_end==2000 && p.vsync_start==1203 && p.vsync_end==1209);
    assert(p.scanout_bytes==9216000 && p.scanout_offset==0 && p.sync_polarity==1);
    // Each protected bit in either sample must reject the plan. Frame counters
    // and unrelated control bits are intentionally not configuration identity.
    for (unsigned pass=0;pass<2;++pass) for (unsigned i=0;i<count;++i) for (unsigned bit=0;bit<32;++bit) {
        if (!(phx_hp_display_expected[i].mask & (1u<<bit))) continue;
        t[pass][i]^=1u<<bit;assert(!valid() && p.version==0);t[pass][i]^=1u<<bit;
    }
    t[1][13]=0xffffff;assert(valid());
    assert(!valid(1919) && !valid(1920,1199) && !valid(1920,1200,7684) && !valid(1920,1200,7680,24));
    m.physical_base+=4096;assert(!valid());m.physical_base-=4096;
    m.cpu_aperture_bytes=4096;assert(!valid());m.cpu_aperture_bytes=256ull<<20;
    info.extraDecoded=false;assert(!valid());
    puts("[PASS] captured HP console plan, timing identity, geometry and reservation rejection");
}
