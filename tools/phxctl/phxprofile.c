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
    if (argc!=1 && !dump) { fprintf(stderr,"phxprofile [--dump-vbios NEW_FILE (sudo, build 37+)]\n");return 2; }
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
    if (conn) IOServiceClose(conn);
    if (kr || size != sizeof(p) || !phx_topology_valid(&p)) {
        fprintf(stderr, "captured profile unavailable or invalid (0x%x); older 780M kernels do not provide it\n", kr);
        return 1;
    }
    printf("PCI %04x:%04x rev %02x subsystem %04x:%04x\n", p.vendor, p.device, p.revision, p.subvendor, p.subdevice);
    printf("CAPTURED metadata, not a live fuse read: %u CUs, %u SE, %u SA/SE, %u physical CU slots/SA, RB mask 0x%x\n",
           p.cu_active_number, p.num_shader_engines, p.num_shader_arrays_per_engine, p.num_cu_per_sh, p.enabled_rb_pipes_mask);
    for (unsigned se = 0; se < p.num_shader_engines; ++se)
        for (unsigned sa = 0; sa < p.num_shader_arrays_per_engine; ++sa)
            printf("SE%u/SA%u CU mask 0x%08x\n", se, sa, p.cu_bitmap[se][sa]);
    printf("Runtime readiness: %s\n", p.flags & PHX_TOPOLOGY_RUNTIME_READY ? "reported by kernel" : "NOT VALIDATED");
    return 0;
}
