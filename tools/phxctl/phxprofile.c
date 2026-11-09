/* SPDX-License-Identifier: MIT
 * clang -arch x86_64 -Wall -Wextra -Werror phxprofile.c -framework IOKit -framework CoreFoundation -o phxprofile
 * ./phxprofile prints captured metadata only. No registers are written.
 */
#include <IOKit/IOKitLib.h>
#include <CoreFoundation/CFNumber.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include "../../src/amd/phx_topology.h"
#include "../../src/amd/phx_vbios_abi.h"
#include "../../src/amd/phx_memory_layout.h"
#include "../../src/amd/phx_reservation_regs.h"

static int scanout(io_connect_t conn,const struct phx_topology *p,int reservations) {
    const struct phx_scanout_register *registers=reservations?phx_reservation_registers:phx_scanout_registers;
    const size_t count=reservations?PHX_RESERVATION_REG_COUNT:PHX_SCANOUT_REG_COUNT;
    if (!phx_topology_matches(p,0x1002,0x1900,0xca,0x103c,0x8c6a)) {
        fprintf(stderr,"scanout register profile requires the exact HP GPU\n");return 1;
    }
    struct phx_memory_layout memory={0};size_t bytes=sizeof(memory);
    kern_return_t kr=IOConnectCallStructMethod(conn,PHX_SEL_MEMORY_LAYOUT,NULL,0,&memory,&bytes);
    if (kr || bytes!=sizeof(memory) || !phx_memory_layout_valid(&memory)) {
        fprintf(stderr,"valid runtime memory query required (0x%x)\n",kr);return 1;
    }
    uint32_t values[2][PHX_RESERVATION_REG_COUNT];
    for (unsigned sample=0;sample<2;++sample) for (size_t i=0;i<count;++i) {
        const uint64_t input[3]={registers[i].dword,1,0xffffffffull};
        bytes=sizeof(uint32_t);
        kr=IOConnectCallMethod(conn,2,input,3,NULL,0,NULL,NULL,&values[sample][i],&bytes);
        if (kr || bytes!=sizeof(uint32_t)) {
            fprintf(stderr,"read-only scanout register 0x%x failed (0x%x); administrator access required\n",
                    registers[i].dword,kr);return 1;
        }
    }
    printf("{\"format\":1,\"atomic\":false,\"register_writes\":false,\"gpu_commands_submitted\":false,"
           "\"acceleration_verified\":false,\"memory\":{\"mc_base\":%llu,\"physical_base\":%llu,"
           "\"vram_bytes\":%llu,\"aperture_base\":%llu,\"aperture_bytes\":%llu,\"flags\":%u},\"samples\":[",
           (unsigned long long)memory.mc_base,(unsigned long long)memory.physical_base,
           (unsigned long long)memory.vram_bytes,(unsigned long long)memory.cpu_aperture_base,
           (unsigned long long)memory.cpu_aperture_bytes,memory.flags);
    for (unsigned sample=0;sample<2;++sample) {
        printf("%s[",sample?",":"");
        for (size_t i=0;i<count;++i)
            printf("%s{\"name\":\"%s\",\"dword\":%u,\"value\":%u}",i?",":"",
                   registers[i].name,registers[i].dword,values[sample][i]);
        printf("]");
    }
    printf("]}\n");return 0;
}

static int dump_vbios(io_connect_t conn, const char *path, uint64_t bytes) {
    int fd=open(path,O_WRONLY|O_CREAT|O_EXCL,0600);
    if (fd<0) { perror("create VBIOS snapshot (new file required)"); return 1; }
    for (uint64_t offset=0;offset<bytes;) {
        uint64_t count=bytes-offset;
        if (count>PHX_VBIOS_READ_MAX) count=PHX_VBIOS_READ_MAX;
        uint64_t input[2]={offset,count}; uint8_t buffer[PHX_VBIOS_READ_MAX]; size_t size=(size_t)count;
        kern_return_t kr=IOConnectCallMethod(conn,PHX_SEL_VBIOS_READ,input,2,NULL,0,NULL,NULL,buffer,&size);
        if (kr || size!=count) {
            fprintf(stderr,"cached VBIOS read failed (0x%x); root is required; no firmware was executed\n",kr);
            close(fd);unlink(path);return 1;
        }
        size_t written=0;
        while (written<size) {
            ssize_t n=write(fd,buffer+written,size-written);
            if (n<0 && errno==EINTR) continue;
            if (n<=0) { perror("write VBIOS snapshot");close(fd);unlink(path);return 1; }
            written+=(size_t)n;
        }
        offset+=count;
    }
    // A sudo caller can retrieve its own private capture over the existing SSH key.
    const char *uid=getenv("SUDO_UID"), *gid=getenv("SUDO_GID");
    if (geteuid()==0 && uid && gid) {
        char *ue=NULL,*ge=NULL;
        unsigned long long u=strtoull(uid,&ue,10),g=strtoull(gid,&ge,10);
        if (*uid && *gid && !*ue && !*ge && u>0 && u<=UINT32_MAX && g<=UINT32_MAX &&
            fchown(fd,(uid_t)u,(gid_t)g)) {
            perror("assign snapshot to invoking user");close(fd);unlink(path);return 1;
        }
    }
    if (fsync(fd)) { perror("sync snapshot");close(fd);unlink(path);return 1; }
    if (close(fd)) { perror("close snapshot");unlink(path);return 1; }
    printf("Saved %llu cached VBIOS bytes to %s; no firmware execution or GPU submission\n",
           (unsigned long long)bytes,path);
    return 0;
}

int main(int argc,char **argv) {
    int dump=argc==3 && !strcmp(argv[1],"--dump-vbios");
    int reservations=argc==2 && !strcmp(argv[1],"--reservations");
    int registers=reservations || (argc==2 && !strcmp(argv[1],"--scanout"));
    if (argc!=1 && !dump && !registers) {
        fprintf(stderr,"phxprofile [--dump-vbios NEW_FILE (sudo, build 37+)] | --scanout | --reservations (sudo, HP, read-only JSON)\n");return 2;
    }
    io_service_t svc = IOServiceGetMatchingService(kIOMainPortDefault, IOServiceMatching("PhxBringup"));
    if (!svc) { fprintf(stderr, "PhxBringup is not loaded\n"); return 1; }
    io_connect_t conn = IO_OBJECT_NULL;
    kern_return_t kr = IOServiceOpen(svc, mach_task_self(), 0x4e34384e, &conn);
    int64_t image_bytes=0;
    if (dump && !kr) {
        CFTypeRef value=IORegistryEntryCreateCFProperty(svc,CFSTR("phx-vbios-image-bytes"),kCFAllocatorDefault,0);
        if (!value || CFGetTypeID(value)!=CFNumberGetTypeID() ||
            !CFNumberGetValue((CFNumberRef)value,kCFNumberSInt64Type,&image_bytes) || image_bytes<=0 || image_bytes>UINT32_MAX)
            kr=kIOReturnNotReady;
        if (value) CFRelease(value);
    }
    IOObjectRelease(svc);
    uint64_t in[2] = {1, 0}, out[4]; uint32_t count = 4;
    if (!kr) kr = IOConnectCallScalarMethod(conn, 0, in, 2, out, &count);
    if (!kr && count!=4) kr=kIOReturnBadArgument;
    if (dump) {
        int result=1;
        if (kr) fprintf(stderr,"VBIOS snapshot unavailable (0x%x); cached VFCT image and build 37+ required\n",kr);
        else result=dump_vbios(conn,argv[2],(uint64_t)image_bytes);
        if (conn) IOServiceClose(conn);
        return result;
    }
    struct phx_topology p = {0}; size_t size = sizeof(p);
    if (!kr && count != 4) kr = kIOReturnBadArgument;
    if (!kr) kr = IOConnectCallStructMethod(conn, PHX_SEL_TOPOLOGY, NULL, 0, &p, &size);
    if (kr || size != sizeof(p) || !phx_topology_valid(&p)) {
        if (conn) IOServiceClose(conn);
        fprintf(stderr, "captured profile unavailable or invalid (0x%x); older 780M kernels do not provide it\n", kr);
        return 1;
    }
    if (registers) { int result=scanout(conn,&p,reservations);IOServiceClose(conn);return result; }
    if (conn) IOServiceClose(conn);
    printf("PCI %04x:%04x rev %02x subsystem %04x:%04x\n", p.vendor, p.device, p.revision, p.subvendor, p.subdevice);
    printf("CAPTURED metadata, not a live fuse read: %u CUs, %u SE, %u SA/SE, %u physical CU slots/SA, RB mask 0x%x\n",
           p.cu_active_number, p.num_shader_engines, p.num_shader_arrays_per_engine, p.num_cu_per_sh, p.enabled_rb_pipes_mask);
    for (unsigned se = 0; se < p.num_shader_engines; ++se)
        for (unsigned sa = 0; sa < p.num_shader_arrays_per_engine; ++sa)
            printf("SE%u/SA%u CU mask 0x%08x\n", se, sa, p.cu_bitmap[se][sa]);
    printf("Runtime readiness: %s\n", p.flags & PHX_TOPOLOGY_RUNTIME_READY ? "reported by kernel" : "NOT VALIDATED");
    return 0;
}
