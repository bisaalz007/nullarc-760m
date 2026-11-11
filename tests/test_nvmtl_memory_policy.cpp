// SPDX-License-Identifier: MIT
#include "nmplugin/nvmtl_memory_policy.h"
#include <cassert>
#include <cstdint>
int main()
{
    constexpr uint64_t MiB=UINT64_C(1)<<20, GiB=UINT64_C(1)<<30;
    assert(nvmtl_default_reserve(GiB,512*MiB,1)==32*MiB);
    assert(nvmtl_default_reserve(2655*MiB,512*MiB,1)==32*MiB);
    assert(nvmtl_working_set_limit(412*MiB,512*MiB,1)==412*MiB);
    assert(nvmtl_working_set_limit(2*GiB,512*MiB,1)==512*MiB);
    assert(nvmtl_working_set_limit(0,512*MiB,1)==0);
    // Preserve reference-size heaps and discrete-device defaults.
    assert(nvmtl_default_reserve(GiB,6*GiB,1)==GiB);
    assert(nvmtl_default_reserve(2655*MiB,6*GiB,1)==2655*MiB);
    assert(nvmtl_default_reserve(GiB,512*MiB,0)==GiB);
    assert(nvmtl_default_reserve(GiB,0,1)==GiB);
    assert(nvmtl_working_set_limit(412*MiB,6*GiB,1)==GiB);
    assert(nvmtl_working_set_limit(412*MiB,512*MiB,0)==GiB);
    assert(nvmtl_working_set_limit(UINT64_MAX,512*MiB,1)==512*MiB);
}
