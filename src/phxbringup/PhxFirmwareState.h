/* SPDX-License-Identifier: MIT
 * The validated Phoenix plan's engine payloads (TOC is a separate command).
 * RLC_G is last; autoload requires every acknowledged payload, not just TMR.
 */
#ifndef PHX_FIRMWARE_STATE_H
#define PHX_FIRMWARE_STATE_H
#include <stdint.h>
class PhxFirmwareState {
    uint32_t loaded{0};
public:
    static constexpr uint32_t types[17]={2,1,4,71,72,33,34,81,82,68,69,20,21,26,48,25,8};
    int index(uint32_t type) const { for (unsigned i=0;i<17;++i) if (types[i]==type) return (int)i;return -1; }
    bool mayLoad(uint32_t type) const {
        const int i=index(type);return i>=0 && (type!=8 || (loaded&0xffffu)==0xffffu);
    }
    void acknowledge(uint32_t type,bool transport,uint64_t status) {
        const int i=index(type);if (i>=0 && transport && status==0) loaded|=1u<<i;
    }
    bool complete() const { return loaded==0x1ffffu; }
    void reset() { loaded=0; }
};
#endif
