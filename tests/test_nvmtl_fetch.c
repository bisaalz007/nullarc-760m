/* SPDX-License-Identifier: MIT */
#include "nmplugin/nvmtl_fetch_spirv.h"
#include <assert.h>
#include <stdio.h>
int main(int argc,char **argv)
{
    assert(argc==3);FILE *in=fopen(argv[1],"rb");assert(in);
    assert(!fseek(in,0,SEEK_END));long bytes=ftell(in);assert(bytes>=20 && bytes%4==0);rewind(in);
    uint32_t *spv=malloc((size_t)bytes);assert(spv);assert(fread(spv,(size_t)bytes,1,in)==1);fclose(in);
    const size_t words=(size_t)bytes/4;size_t n=0;uint32_t mask=0,*out=NULL;
    assert(!nvmtl_prepare_fetch(spv,words,5,&mask,&out,&n) && mask==5 && !out && n==words);
    assert(!nvmtl_prepare_fetch(spv,words,1,&mask,&out,&n) && mask==1 && out);
    unsigned reads=0,zeros=0;
    for(size_t i=5;i<n;i+=out[i]>>16){reads+=(out[i]&0xffffu)==NFS_READ;zeros+=(out[i]&0xffffu)==NFS_NULL;}
    assert(reads==1 && zeros==1);
    FILE *dest=fopen(argv[2],"wb");assert(dest);assert(fwrite(out,4,n,dest)==n);assert(!fclose(dest));free(out);
    spv[5]=0;
    assert(nvmtl_prepare_fetch(spv,words,1,&mask,&out,&n)==-1 && !out);
    free(spv);puts("[PASS] absent input becomes typed zero; present framebuffer read remains");
}
