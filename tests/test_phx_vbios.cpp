#include "amd/phx_vbios.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <vector>

using Bytes=std::vector<uint8_t>;
static void w16(Bytes &b,size_t p,uint16_t x) { b.at(p)=(uint8_t)x; b.at(p+1)=(uint8_t)(x>>8); }
static void w32(Bytes &b,size_t p,uint32_t x) { w16(b,p,(uint16_t)x);w16(b,p+2,(uint16_t)(x>>16)); }
static void checksum(Bytes &b) {
    b[9]=0; uint8_t sum=0;for(auto v:b)sum=(uint8_t)(sum+v);b[9]=(uint8_t)(0-sum);
}
static Bytes fixture() {
    Bytes rom(512);rom[0]=0x55;rom[1]=0xaa;rom[2]=1;w16(rom,0x48,0x80);
    w16(rom,0x80,36);rom[0x82]=2;rom[0x83]=2;memcpy(rom.data()+0x84,"ATOM",4);w16(rom,0xa0,0xc0);
    w16(rom,0xc0,28);rom[0xc2]=2;rom[0xc3]=1;w16(rom,0xcc,0x140);w16(rom,0xda,0x100);
    w16(rom,0x100,48);rom[0x102]=2;rom[0x103]=2;
    w32(rom,0x104,0x8000);w16(rom,0x108,64);w32(rom,0x10c,0x4000);w32(rom,0x110,32);
    w16(rom,0x140,172);rom[0x142]=3;rom[0x143]=5;w32(rom,0x144,0x12345678);
    w32(rom,0x140+20,128);w32(rom,0x140+84,256);
    Bytes b(76+28);memcpy(b.data(),"VFCT",4);w32(b,52,76);
    w32(b,76,1);w32(b,80,0);w32(b,84,0);w16(b,88,0x1002);w16(b,90,0x1900);w32(b,100,512);
    b.insert(b.end(),rom.begin(),rom.end());w32(b,4,(uint32_t)b.size());checksum(b);return b;
}
static PhxVbiosResult decode(const Bytes &b,PhxVbiosInfo &p) {
    return phxDecodeVfct(b.data(),b.size(),1,0,0,0x1002,0x1900,p);
}
int main() {
    const auto good=fixture();PhxVbiosInfo p{};
    assert(decode(good,p)==PhxVbiosResult::Decoded);
    assert(p.imageBytes==512 && p.firmwareRevision==0x12345678 && p.usageDecoded);
    assert(p.firmwareUsageBytes==64*1024 && p.driverUsageBytes==32*1024);
    assert(p.extraDecoded && p.extraFirmwareBytes==256*1024);
    assert(p.protectedDecoded && p.protectedFirmwareBytes==128*1024);
    auto b=good;b[104+0x143]=4; // firmware table 3.4 has no protected-size field
    checksum(b);assert(decode(b,p)==PhxVbiosResult::Decoded && !p.protectedDecoded && p.extraDecoded);
    b=good;b[104+0x143]=6;checksum(b);
    assert(decode(b,p)==PhxVbiosResult::Decoded && !p.protectedDecoded && !p.extraDecoded);
    b=good;b[104+0x103]=1;w16(b,104+0x100,12);checksum(b);
    assert(decode(b,p)==PhxVbiosResult::Decoded && p.usageContent==1 && p.driverStartRawKiB==0);
    b=good;w16(b,104+0x140,100);checksum(b);assert(decode(b,p)==PhxVbiosResult::Invalid);
    b=good;w32(b,80,1);checksum(b);assert(decode(b,p)==PhxVbiosResult::MissingImage);
    b=good;b[104+0x82]=9;checksum(b);assert(decode(b,p)==PhxVbiosResult::Unsupported);
    b=good;b[9]++;assert(decode(b,p)==PhxVbiosResult::Invalid);
    b=good;w32(b,52,UINT32_MAX);checksum(b);assert(decode(b,p)==PhxVbiosResult::Invalid);
    b=good;w32(b,100,UINT32_MAX);checksum(b);assert(decode(b,p)==PhxVbiosResult::Invalid);
    b=good;w16(b,104+0xa0,0xffff);checksum(b);assert(decode(b,p)==PhxVbiosResult::Invalid);
    b=good;b.insert(b.end(),good.begin()+76,good.end());w32(b,4,(uint32_t)b.size());checksum(b);
    assert(decode(b,p)==PhxVbiosResult::Invalid); // duplicate device image
    for (size_t length=0;length<good.size();++length) {
        p.imageBytes=0xabcdef;
        assert(phxDecodeVfct(good.data(),length,1,0,0,0x1002,0x1900,p)==PhxVbiosResult::Invalid);
        assert(p.imageBytes==0xabcdef); // no partial publication
    }
    uint32_t seed=0x760;
    for (unsigned i=0;i<10000;++i) {
        b=good;seed=seed*1664525+1013904223;size_t index=seed%b.size();
        seed=seed*1664525+1013904223;b[index]^=(uint8_t)(seed>>16);checksum(b);
        (void)decode(b,p); // malformed table offsets and sizes under sanitizers
    }
    puts("[PASS] VFCT device selection, ATOM fields, version limits, truncation, ambiguity and 10000 mutations");
}
