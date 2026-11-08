/* SPDX-License-Identifier: MIT
 * Bounds-checked, read-only VFCT/ATOM metadata decoder. Layout references:
 * Linux v6.14 amd/include/atomfirmware.h and amdgpu/amdgpu_bios.c.
 * These firmware claims do not establish ownership or permit GPU writes.
 */
#ifndef PHX_VBIOS_H
#define PHX_VBIOS_H
#include <stdint.h>
#include <stddef.h>

enum class PhxVbiosResult { Decoded, MissingImage, Invalid, Unsupported };
struct PhxVbiosInfo {
    uint32_t romFormat, romContent, masterFormat, masterContent;
    uint32_t imageBytes, firmwareRevision, firmwareFormat, firmwareContent;
    uint32_t usageFormat, usageContent, firmwareStartRawKiB, driverStartRawKiB;
    uint64_t firmwareUsageBytes, driverUsageBytes, extraFirmwareBytes, protectedFirmwareBytes;
    bool usageDecoded, extraDecoded, protectedDecoded, romHeaderKnown, masterHeaderKnown;
};
static inline uint16_t phxVbios16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}
static inline uint32_t phxVbios32(const uint8_t *p) {
    return (uint32_t)phxVbios16(p) | ((uint32_t)phxVbios16(p+2) << 16);
}
static inline bool phxVbiosSpan(size_t offset, size_t bytes, size_t size) {
    return bytes && offset <= size && bytes <= size-offset;
}
static inline bool phxVbiosTable(const uint8_t *rom, size_t size, size_t offset, size_t minimum) {
    return offset && phxVbiosSpan(offset,4,size) && phxVbios16(rom+offset)>=minimum &&
           phxVbiosSpan(offset,phxVbios16(rom+offset),size);
}
static inline PhxVbiosResult phxDecodeAtom(const uint8_t *rom, size_t size, PhxVbiosInfo &out) {
    if (!rom || size>UINT32_MAX || !phxVbiosSpan(0,0x4a,size) || rom[0]!=0x55 || rom[1]!=0xaa)
        return PhxVbiosResult::Invalid;
    const size_t header=phxVbios16(rom+0x48);
    if (!phxVbiosTable(rom,size,header,36)) return PhxVbiosResult::Invalid;
    const uint8_t *h=rom+header;
    if (!((h[4]=='A'&&h[5]=='T'&&h[6]=='O'&&h[7]=='M') ||
          (h[4]=='M'&&h[5]=='O'&&h[6]=='T'&&h[7]=='A'))) return PhxVbiosResult::Invalid;
    PhxVbiosInfo p{};
    p.imageBytes=(uint32_t)size; p.romHeaderKnown=true; p.romFormat=h[2]; p.romContent=h[3];
    if (h[2]!=2 || h[3]!=2) { out=p; return PhxVbiosResult::Unsupported; }
    const size_t master=phxVbios16(h+32);
    if (!phxVbiosTable(rom,size,master,28)) return PhxVbiosResult::Invalid;
    p.masterHeaderKnown=true; p.masterFormat=rom[master+2]; p.masterContent=rom[master+3];
    if (p.masterFormat!=2 || p.masterContent!=1) { out=p; return PhxVbiosResult::Unsupported; }
    // Master data-table indexes: firmwareinfo=4, vram_usagebyfirmware=11.
    const size_t fw=phxVbios16(rom+master+4+4*2), usage=phxVbios16(rom+master+4+11*2);
    if (!phxVbiosTable(rom,size,fw,8)) return PhxVbiosResult::Invalid;
    p.firmwareFormat=rom[fw+2]; p.firmwareContent=rom[fw+3];
    p.firmwareRevision=phxVbios32(rom+fw+4);
    if (p.firmwareFormat==3 && (p.firmwareContent==4 || p.firmwareContent==5)) {
        const size_t minimum=p.firmwareContent==4 ? 108 : 172;
        if (!phxVbiosTable(rom,size,fw,minimum)) return PhxVbiosResult::Invalid;
        p.extraFirmwareBytes=(uint64_t)phxVbios32(rom+fw+84)<<10;
        p.extraDecoded=true;
        if (p.firmwareContent==5) {
            p.protectedFirmwareBytes=(uint64_t)phxVbios32(rom+fw+20)<<10;
            p.protectedDecoded=true;
        }
    }
    if (usage) {
        if (!phxVbiosTable(rom,size,usage,4)) return PhxVbiosResult::Invalid;
        p.usageFormat=rom[usage+2]; p.usageContent=rom[usage+3];
        if (p.usageFormat==2 && (p.usageContent==1 || p.usageContent==2)) {
            if (!phxVbiosTable(rom,size,usage,p.usageContent==1 ? 12 : 48)) return PhxVbiosResult::Invalid;
            p.firmwareStartRawKiB=phxVbios32(rom+usage+4);
            p.firmwareUsageBytes=(uint64_t)phxVbios16(rom+usage+8)<<10;
            if (p.usageContent==1) {
                // v2.1 has no explicit driver start. Preserve the raw claim only.
                p.driverUsageBytes=(uint64_t)phxVbios16(rom+usage+10)<<10;
            } else {
                p.driverStartRawKiB=phxVbios32(rom+usage+12);
                p.driverUsageBytes=(uint64_t)phxVbios32(rom+usage+16)<<10;
            }
            p.usageDecoded=true;
        }
    }
    out=p;
    return PhxVbiosResult::Decoded;
}
struct PhxVbiosView { const uint8_t *bytes; size_t size; };
static inline PhxVbiosResult phxFindVfctImage(const uint8_t *table, size_t size,
    uint32_t bus, uint32_t device, uint32_t function, uint16_t vendor, uint16_t gpu,
    PhxVbiosView &out) {
    if (!table || size<76 || table[0]!='V'||table[1]!='F'||table[2]!='C'||table[3]!='T')
        return PhxVbiosResult::Invalid;
    const size_t length=phxVbios32(table+4);
    if (length<76 || length>size) return PhxVbiosResult::Invalid;
    uint8_t checksum=0;
    for (size_t i=0;i<length;++i) checksum=(uint8_t)(checksum+table[i]);
    if (checksum) return PhxVbiosResult::Invalid;
    size_t offset=phxVbios32(table+52), selected=0, selectedSize=0;
    if (!offset) return PhxVbiosResult::MissingImage;
    if (offset<76 || !phxVbiosSpan(offset,28,length)) return PhxVbiosResult::Invalid;
    while (offset<length) {
        if (!phxVbiosSpan(offset,28,length)) return PhxVbiosResult::Invalid;
        const uint8_t *h=table+offset;
        const size_t bytes=phxVbios32(h+24);
        offset+=28;
        if (bytes && !phxVbiosSpan(offset,bytes,length)) return PhxVbiosResult::Invalid;
        if (bytes && phxVbios32(h)==bus && phxVbios32(h+4)==device && phxVbios32(h+8)==function &&
            phxVbios16(h+12)==vendor && phxVbios16(h+14)==gpu) {
            if (selected) return PhxVbiosResult::Invalid; // ambiguous device image
            selected=offset; selectedSize=bytes;
        }
        offset+=bytes;
    }
    if (!selected) return PhxVbiosResult::MissingImage;
    out={table+selected,selectedSize};
    return PhxVbiosResult::Decoded;
}
static inline PhxVbiosResult phxDecodeVfct(const uint8_t *table, size_t size,
    uint32_t bus, uint32_t device, uint32_t function, uint16_t vendor, uint16_t gpu,
    PhxVbiosInfo &out) {
    PhxVbiosView view{};
    const auto result=phxFindVfctImage(table,size,bus,device,function,vendor,gpu,view);
    return result==PhxVbiosResult::Decoded ? phxDecodeAtom(view.bytes,view.size,out) : result;
}
#endif
