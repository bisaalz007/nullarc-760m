#!/bin/bash
# Phoenix GFX power-up in the Linux driver's order: PSP ring, TOC and TMR, the firmware of every engine through
# LOAD_IP_FW, RLC autoload, then the SMU messages that switch GFX on (EnableGfxImu with 1). Firmware from ~/gpu/fw at
# header-derived ranges of linux-firmware's gc_11_0_1/psp_13_0_4 files. Run as root (phxboot) or as a user with sudo.
# A reboot is armed for 3 minutes in case the PSP hangs and cancelled at the end.
set -eo pipefail
REGISTRY=$(ioreg -rc PhxBringup -l)
if ! grep -q '"phx-build"' <<<"$REGISTRY"; then
    echo "PhxBringup is not loaded; bring-up stopped before watchdog or hardware access." >&2
    exit 1
fi
if grep -qE '"phx-stage" = "(profile-diagnostic-only|device-lost)"' <<<"$REGISTRY"; then
    echo "Diagnostic-only or lost GPU: bring-up refused; collect evidence or reboot." >&2
    exit 1
fi
# Parse every file before any watchdog, PSP command or staging write. The planner
# retains the reference staging allocation; this does not enable the HP device.
FW_PLAN=$(~/gpu/phxctl/phxfw --phoenix-plan ~/gpu/fw)
IFS=$'\t' read -r TOC_FILE TOC_OFFSET TOC_SIZE TOC_TYPE TOC_STAGE <<<"$FW_PLAN"
[ "$TOC_TYPE" = 0 ] || { echo "Invalid firmware plan TOC" >&2; exit 1; }
SUDO=""; [ "$(id -u)" = 0 ] || SUDO=sudo
P(){ $SUDO ~/gpu/phxctl/phxctl "$@"; }
echo "== watchdog: reboot in 3 min unless cancelled =="
$SUDO bash -c 'nohup shutdown -r +3 >/dev/null 2>&1 &'
P psp destroy >/dev/null 2>&1 || true
P psp create 0x1100000 >/dev/null
P stage "$HOME/gpu/fw/$TOC_FILE" "$TOC_OFFSET" "$TOC_SIZE" "$TOC_STAGE" >/dev/null
P raw 0x20 0x04000000 0x80 "$TOC_SIZE" 0 0 0 >/dev/null
P raw 0x5 0x08000000 0x80 0x4000000 0x2 0x0C000000 0x6A >/dev/null
echo "== load firmware =="
L(){ P loadfw "$@" 2>&1 | grep loadfw >> ~/gpu/fwaddr.log; }
: > ~/gpu/fwaddr.log
while IFS=$'\t' read -r FILE OFFSET SIZE TYPE STAGE; do
    [ "$TYPE" != 0 ] || continue
    L "$HOME/gpu/fw/$FILE" "$OFFSET" "$SIZE" "$TYPE" "$STAGE"
done <<<"$FW_PLAN"
echo "== AUTOLOAD_RLC =="
P autoload
echo "== SMU 0x3, 0x2, EnableGfxImu(param=1) (linux order) =="
P smu 0x3 0 | tail -1
P smu 0x2 0 | tail -1
P smu 0x16 1 | tail -1
sleep 2
P regs 0xee7e 0x21a0 0x2004 0x263e
$SUDO killall shutdown 2>/dev/null || true
echo "firmware/power stage complete; watchdog cancellation requested"
