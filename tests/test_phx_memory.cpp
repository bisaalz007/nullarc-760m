#include "amd/phx_memory_layout.h"
#include "phxbringup/PhxNativeABI.h"
#include <cassert>
#include <cstddef>
#include <cstdio>
#include <initializer_list>
int main() {
    static_assert(sizeof(phx_memory_layout) == 80, "wire ABI");
    static_assert(offsetof(phx_memory_layout, mc_base) == 24, "C/C++ ABI");
    phx_memory_layout p{};
    p.version=1; p.flags=PHX_MEMORY_DECODED|PHX_MEMORY_DIAGNOSTIC_ONLY;
    p.raw_base=0x8000; p.raw_top=0x801f; p.raw_offset=0x260;
    p.mc_base=0x8000000000ull; p.physical_base=0x260000000ull; p.vram_bytes=512ull<<20;
    p.cpu_aperture_base=0x2b0000000ull; p.cpu_aperture_bytes=256ull<<20;
    assert(phx_memory_layout_valid(&p));
    uint64_t mc=1, physical=2;
    assert(phx_memory_translate(&p, p.vram_bytes-4096,4096,&mc,&physical));
    assert(mc==p.mc_base+p.vram_bytes-4096 && physical==p.physical_base+p.vram_bytes-4096);
    const uint64_t saved_mc=mc, saved_physical=physical;
    for (auto off : {p.vram_bytes, UINT64_MAX}) {
        assert(!phx_memory_translate(&p,off,4096,&mc,&physical));
        assert(mc==saved_mc && physical==saved_physical);
    }
    assert(!phx_memory_translate(&p,0,0,&mc,&physical));
    assert(!phx_memory_translate(&p,0,1,nullptr,&physical));
    auto q=p; ++q.physical_base; assert(!phx_memory_layout_valid(&q));
    q=p; q.reserved[1]=1; assert(!phx_memory_layout_valid(&q));
    q=p; q.flags|=8; assert(!phx_memory_layout_valid(&q));
    q=p; q.version=2; assert(!phx_memory_layout_valid(&q));
    q=p; q.raw_offset=UINT32_MAX; assert(!phx_memory_layout_valid(&q));
    q=p; q.cpu_aperture_base=UINT64_MAX-4095; assert(!phx_memory_layout_valid(&q));
    q=p; q.cpu_aperture_base=q.cpu_aperture_bytes=0; assert(phx_memory_layout_valid(&q));
    q=p; q.raw_top=0x817f; q.raw_offset=0x6a0; q.physical_base=0x6a0000000ull; q.vram_bytes=6ull<<30;
    assert(phx_memory_layout_valid(&q)); // Reference memory remains representable.
    for (unsigned selector=0;selector<120;++selector)
        assert(phxDiagnosticSelector(selector)==(selector==31 || selector==32 || selector==33 || phx_topology_diagnostic_selector(selector)));
    puts("[PASS] runtime memory ABI, HP/reference addressing, malformed data, spans and selector policy");
}
