/* SPDX-License-Identifier: MIT
 * Root-only cached VBIOS snapshot. No ROM BAR/MMIO access or firmware execution.
 * Scalar input: byte offset, byte count. Structure output: exactly byte count.
 */
#ifndef PHX_VBIOS_ABI_H
#define PHX_VBIOS_ABI_H
#define PHX_SEL_VBIOS_READ 32u
#define PHX_VBIOS_READ_MAX 4096u
#endif
