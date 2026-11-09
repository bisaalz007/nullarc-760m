#!/bin/bash
# full.sh <mesboot step>: power the GPU up (bringup5.sh), open the doorbells, unhalt the CP and start MES with the GART,
# then run one mesboot step with its options from the environment (phxboot: MC=1 CS=1 ADOPT=1 GFX=1 AG=1 ... kiqsched).
# Run as root (phxboot) or as a user with sudo. A reboot is armed for 4 minutes in case the GPU hangs the bus.
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
SUDO=""; [ "$(id -u)" = 0 ] || SUDO=sudo
MES_PCS=$(~/gpu/phxctl/phxfw --mes-start-pcs ~/gpu/fw)
read -r MES_SCHED_PC MES_KIQ_PC <<<"$MES_PCS"
bash ~/gpu/bringup5.sh
$SUDO bash -c "nohup shutdown -r +4 >/dev/null 2>&1 &"
$SUDO ~/gpu/phxctl/phxctl wreg 0xDE0 1 | tail -1
$SUDO ~/gpu/phxctl/phxctl wreg 0xA802 0 | tail -1
$SUDO ~/gpu/phxctl/phxctl wreg 0xA803 0x01000000 | tail -1
$SUDO ~/gpu/phxctl/mesboot gart
$SUDO env MESBOOT_SCHED_PC="$MES_SCHED_PC" MESBOOT_KIQ_PC="$MES_KIQ_PC" ~/gpu/phxctl/mesboot mes
$SUDO env MESBOOT_SCHED_PC="$MES_SCHED_PC" MESBOOT_KIQ_PC="$MES_KIQ_PC" MESBOOT_MC=$MC MESBOOT_CS=$CS MESBOOT_VMT=$VMT PTE_SYS=$PS PTE_NOFB=$NF FAULT_DEFAULT=$FD PT_SYS=$PTS VARONLY=$VAR PTE_EXTRA=$PX ROOT_FL=$RF AGPTEST=$AGP CTX0_OFF=$C0 VM8=$V8 VM8_MT=$VMT8 IB0=$IB0 VM8_FLAT=$FLAT VM8_SYS=$VSYS ADOPT=$ADOPT MESBOOT_GFX=$GFX ADOPT_GFX=$AG VM8_IBSYS=$IBSYS VM8_HI=$VHI ~/gpu/phxctl/mesboot "$1" 2>&1 | tail -12
$SUDO killall shutdown 2>/dev/null || true
