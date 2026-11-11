// SPDX-License-Identifier: MIT
#include <dlfcn.h>
#include <stdint.h>
#include <string.h>
#include <stdio.h>
#include <unistd.h>
#include <sys/types.h>
/* Read-only API: XNU 11417.140.69 bsd/sys/codesign.h, CS_OPS_STATUS=0. */
extern int csops(pid_t, unsigned int, void *, size_t);
int main(int argc,char **argv) {
 if(argc!=2 && !(argc==3 && strcmp(argv[2],"--load-only")==0))return 2;
 uint32_t flags=0;
 if(csops(getpid(),0,&flags,sizeof(flags))!=0){perror("csops status");return 3;}
 void *image=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);
 if(!image){fprintf(stderr,"%s\n",dlerror());printf("{\"flags\":%u,\"loaded\":false}\n",flags);return 1;}
 if(argc==3){printf("{\"flags\":%u,\"loaded\":true}\n",flags);return 0;}
 int (*probe)(void)=(int (*)(void))dlsym(image,"nullarc_policy_probe");
 int value=probe?probe():-1;
 printf("{\"flags\":%u,\"loaded\":true,\"fixture_value\":%d}\n",flags,value);
 return value==0x760?0:4;
}
