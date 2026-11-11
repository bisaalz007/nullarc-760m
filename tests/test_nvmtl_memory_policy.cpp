// SPDX-License-Identifier: MIT
#include "nmplugin/nvmtl_memory_policy.h"
#include "nmplugin/nvmtl_texture_layout.h"
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
    assert(nvmtl_integrated_free(512*MiB,512*MiB,114*MiB,4*MiB)==394*MiB);
    assert(nvmtl_integrated_free(512*MiB,768*MiB,500*MiB,16*MiB)==0);
    assert(nvmtl_integrated_free(512*MiB,320*MiB,64*MiB,0)==256*MiB);
    assert(nvmtl_integrated_free(512*MiB,320*MiB,UINT64_MAX,UINT64_MAX)==0);
    assert(nvmtl_rows_fit(4096,0,128,23,17*4));
    assert(nvmtl_rows_fit(20480,0,192,103,84*2));
    assert(nvmtl_rows_fit(20480,256,960,18,234*4));
    assert(nvmtl_rows_fit(256+17*960+234*4,256,960,18,234*4));
    assert(!nvmtl_rows_fit(256+17*960+234*4-1,256,960,18,234*4));
    assert(!nvmtl_rows_fit(SIZE_MAX,SIZE_MAX-32,SIZE_MAX,2,4));
    assert(!nvmtl_rows_fit(4096,0,32,23,17*4));
}
