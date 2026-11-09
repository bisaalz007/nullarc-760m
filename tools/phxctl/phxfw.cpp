/* SPDX-License-Identifier: MIT
 * Offline Phoenix firmware planner. No IOKit, register access or firmware loads.
 * Header ABI: Linux v6.14 amdgpu_ucode.h / mes_v11_0.c.
 */
#include "../../src/amd/rdna3_ucode_extract.h"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

using namespace rdna3;
struct Entry { const char *name; UcodePayload payload; uint32_t staging; };
struct Input { const char *name; uint64_t kind; unsigned expected; };
static const Input inputs[] = {
    {"psp_13_0_4_toc.bin", kHostFwIPBase, 1},
    {"gc_11_0_1_pfp.bin", kHostFwFile_CP_PFP, 1},
    {"gc_11_0_1_me.bin", kHostFwFile_CP_ME, 1},
    {"gc_11_0_1_mec.bin", kHostFwFile_CP_MEC, 1},
    {"sdma_6_0_1.bin", kHostFwFile_SDMA, 2},
    {"gc_11_0_1_mes_2.bin", kHostFwFile_MES, 2},
    {"gc_11_0_1_mes1.bin", kHostFwFile_MES_KIQ, 2},
    {"gc_11_0_1_imu.bin", kHostFwFile_IMU, 2},
    {"gc_11_0_1_rlc.bin", kHostFwFile_RLC, 6},
};
// Existing reference-machine staging allocation, NOT an HP memory reservation.
// Capacities prevent one firmware payload from overwriting the next slot.
static bool slot(uint32_t type, uint32_t &offset, uint32_t &capacity) {
    capacity = 0x40000;
    switch (type) {
    case 0: offset = 0; return true; // TOC is staged/consumed before IP files
    case 2: offset = 0; capacity = 0x100000; return true;
    case 1: offset = 0x100000; capacity = 0x100000; return true;
    case 4: offset = 0x200000; capacity = 0x100000; return true;
    case 8: offset = 0x300000; capacity = 0x80000; return true;
    case 71: offset = 0x380000; return true;
    case 72: offset = 0x3c0000; return true;
    case 33: offset = 0x400000; return true;
    case 34: offset = 0x440000; return true;
    case 81: offset = 0x480000; return true;
    case 82: offset = 0x4c0000; return true;
    case 68: offset = 0x500000; capacity = 0x100000; return true;
    case 69: offset = 0x600000; capacity = 0x100000; return true;
    case 20: offset = 0x700000; capacity = 0x20000; return true;
    case 21: offset = 0x720000; capacity = 0xe0000; return true;
    case 26: offset = 0x800000; return true;
    case 48: offset = 0x840000; return true;
    case 25: offset = 0x880000; return true;
    default: return false;
    }
}

static bool decode(const std::string &path, uint64_t kind, std::vector<UcodePayload> &payloads, uint64_t *mesPc=nullptr) {
    std::ifstream f(path, std::ios::binary | std::ios::ate);
    if (!f) return false;
    const auto size = f.tellg();
    if (size < static_cast<std::streamoff>(sizeof(common_firmware_header)) || size > 16 * 1024 * 1024) return false;
    std::vector<uint8_t> bytes(static_cast<size_t>(size));
    f.seekg(0);
    if (!f.read(reinterpret_cast<char *>(bytes.data()), size)) return false;
    const auto *h = reinterpret_cast<const common_firmware_header *>(bytes.data());
    if (h->size_bytes != bytes.size() || h->header_size_bytes < sizeof(*h) ||
        h->header_size_bytes > h->ucode_array_offset_bytes ||
        h->ucode_array_offset_bytes > bytes.size() || !h->ucode_size_bytes ||
        h->ucode_size_bytes > bytes.size() - h->ucode_array_offset_bytes) return false;
    // This planner targets the measured Phoenix file families only.
    const bool sdma = kind == kHostFwFile_SDMA, rlc = kind == kHostFwFile_RLC;
    const size_t min_header = sdma ? sizeof(sdma_firmware_header_v2_0) :
        rlc ? sizeof(rlc_firmware_header_v2_3) :
        kind == kHostFwFile_IMU ? sizeof(imu_firmware_header_v1_0) :
        kind == kHostFwFile_MES || kind == kHostFwFile_MES_KIQ ? sizeof(mes_firmware_header_v1_0) : sizeof(*h);
    if (h->header_size_bytes < min_header) return false;
    if (h->header_version_major != (sdma || rlc ? 2 : 1) ||
        h->ip_version_major != (sdma ? 6 : kind == kHostFwIPBase ? 13 : 11)) return false;
    UcodePayload out[kMaxUcodePayloadsPerFile];
    const unsigned count = rdna3_ucode_extract(kind, bytes.data(), bytes.size(), out);
    if (!count) return false;
    for (unsigned i = 0; i < count; ++i) {
        if (out[i].offset_bytes < h->header_size_bytes ||
            out[i].offset_bytes > bytes.size() || !out[i].size_bytes ||
            out[i].size_bytes > bytes.size() - out[i].offset_bytes) return false;
        for (unsigned j = 0; j < i; ++j) {
            if (out[i].fw_type == out[j].fw_type ||
                (uint64_t(out[i].offset_bytes) < uint64_t(out[j].offset_bytes) + out[j].size_bytes &&
                 uint64_t(out[j].offset_bytes) < uint64_t(out[i].offset_bytes) + out[i].size_bytes)) return false;
        }
    }
    payloads.assign(out, out + count);
    if (mesPc) {
        if (kind!=kHostFwFile_MES && kind!=kHostFwFile_MES_KIQ) return false;
        const auto *m=reinterpret_cast<const mes_firmware_header_v1_0 *>(bytes.data());
        *mesPc=(uint64_t(m->mes_uc_start_addr_hi)<<32)|m->mes_uc_start_addr_lo;
        if (!*mesPc || (*mesPc&3)) return false;
    }
    return true;
}

int main(int argc, char **argv) {
    if (argc==3 && !strcmp(argv[1],"--mes-start-pcs")) {
        std::vector<UcodePayload> payloads;uint64_t scheduler=0,kiq=0;
        const std::string dir=argv[2];
        if (!decode(dir+"/gc_11_0_1_mes_2.bin",kHostFwFile_MES,payloads,&scheduler) ||
            !decode(dir+"/gc_11_0_1_mes1.bin",kHostFwFile_MES_KIQ,payloads,&kiq)) {
            fprintf(stderr,"invalid MES entry-point headers\n");return 1;
        }
        printf("0x%llx 0x%llx\n",(unsigned long long)scheduler,(unsigned long long)kiq);return 0;
    }
    if (argc == 4 && !strcmp(argv[1], "--inspect-mes")) {
        if (strcmp(argv[2], "scheduler") && strcmp(argv[2], "kiq")) return 2;
        std::vector<UcodePayload> p;
        if (!decode(argv[3], !strcmp(argv[2], "kiq") ? kHostFwFile_MES_KIQ : kHostFwFile_MES, p)) {
            fprintf(stderr, "invalid MES firmware: %s\n", argv[3]); return 1;
        }
        printf("{\"payloads\":[");
        for (size_t i = 0; i < p.size(); ++i)
            printf("%s{\"fw_type\":%u,\"offset\":%u,\"size\":%u}", i ? "," : "", p[i].fw_type, p[i].offset_bytes, p[i].size_bytes);
        puts("]}"); return 0;
    }
    if (argc != 3 || strcmp(argv[1], "--phoenix-plan")) {
        fprintf(stderr, "usage: phxfw --phoenix-plan DIR | --inspect-mes scheduler|kiq FILE\n"); return 2;
    }
    std::vector<Entry> plan;
    for (const auto &input : inputs) {
        std::vector<UcodePayload> p;
        if (!decode(std::string(argv[2]) + "/" + input.name, input.kind, p) || p.size() != input.expected) {
            fprintf(stderr, "unsupported, missing or corrupt firmware: %s\n", input.name); return 1;
        }
        for (const auto &payload : p) {
            uint32_t offset, capacity;
            if (!slot(payload.fw_type, offset, capacity) || payload.size_bytes > capacity) {
                fprintf(stderr, "unsupported payload/staging capacity: %s type %u\n", input.name, payload.fw_type); return 1;
            }
            plan.push_back({input.name, payload, offset});
        }
    }
    // No stdout until ALL files/ranges/capacities have passed preflight.
    for (const auto &e : plan)
        printf("%s\t%u\t%u\t%u\t%u\n", e.name, e.payload.offset_bytes, e.payload.size_bytes, e.payload.fw_type, e.staging);
    return ferror(stdout) ? 1 : 0;
}
