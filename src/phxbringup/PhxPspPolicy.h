/* SPDX-License-Identifier: MIT
 * Software lifetime policy for the single outstanding PSP command buffer.
 * A timeout does not establish that PSP DMA stopped. Only an acknowledged ring
 * destruction permits reuse. This policy performs no hardware operations.
 */
#ifndef PHX_PSP_POLICY_H
#define PHX_PSP_POLICY_H
#include <stdint.h>
struct PhxPspState {
    bool uncertain{false};
    uint32_t confirmedTmrBytes{0};
    bool reusable() const { return !uncertain; }
    void completed(bool fenceArrived) {
        if (!fenceArrived) { uncertain = true; confirmedTmrBytes = 0; }
    }
    void setupResult(uint32_t bytes, bool transportSucceeded, uint64_t status) {
        confirmedTmrBytes = reusable() && transportSucceeded && status == 0 ? bytes : 0;
    }
    void destroyed(bool acknowledged) {
        uncertain = !acknowledged;
        confirmedTmrBytes = 0;
    }
};
#endif
