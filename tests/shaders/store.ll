; SPDX-License-Identifier: MIT
; Authored AIR-style kernel; no copied Apple shader code.
define void @store_value(ptr addrspace(1) %out) {
entry:
  store i32 7, ptr addrspace(1) %out, align 4
  ret void
}
!air.kernel = !{!0}
!0 = !{ptr @store_value, !1, !2}
!1 = !{}
!2 = !{!3}
!3 = !{i32 0, !"air.buffer", !"air.buffer_size", i32 4, !"air.location_index", i32 0, i32 1, !"air.write", !"air.address_space", i32 1, !"air.arg_type_size", i32 4, !"air.arg_type_align_size", i32 4, !"air.arg_type_name", !"uint", !"air.arg_name", !"out"}
