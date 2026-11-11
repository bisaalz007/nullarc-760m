/* SPDX-License-Identifier: MIT */
#ifndef NVMTL_FETCH_SPIRV_H
#define NVMTL_FETCH_SPIRV_H
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

/* NullMoth v2.4.1 lowers colour reads to a direct OpLoad of a set-3
 * SubpassData variable and OpImageRead. Vulkan forbids reading unused input
 * attachments. Metal leaves an absent colour undefined; choose a typed zero
 * and remove its load. Refuse an unfamiliar use instead of binding an image
 * that is not part of the render pass. Values are from SPIR-V's core grammar. */
enum { NFS_NAME=5, NFS_DECORATE=71, NFS_FUNCTION=54, NFS_LOAD=61,
       NFS_READ=98, NFS_COPY=83, NFS_NULL=46 };
typedef struct { uint32_t set, binding, index, zero; unsigned flags, drop; } nvmtl_fetch_id;

static inline int nvmtl_prepare_fetch(const uint32_t *src,size_t words,uint32_t available,
                                     uint32_t *live,uint32_t **output,size_t *output_words)
{
    *live=0; *output=NULL; *output_words=words;
    if (!src || words<5 || src[0]!=0x07230203u) return -1;
    size_t fn=words; int has_input=0;
    for (size_t i=5;i<words;) {
        const uint32_t op=src[i]&0xffffu,wc=src[i]>>16;
        if (!wc || wc>words-i) return -1;
        if (op==NFS_FUNCTION && fn==words) fn=i;
        if (op==NFS_DECORATE && wc==4 && src[i+2]==43) has_input=1; /* InputAttachmentIndex */
        i+=wc;
    }
    if (!has_input) return 0;
    const uint32_t bound=src[3];
    if (!bound || bound>(1u<<20) || fn==words) return -1;
    nvmtl_fetch_id *ids=(nvmtl_fetch_id *)calloc(bound,sizeof(*ids));
    if (!ids) return -1;
    int rc=-1,missing=0;uint32_t *dst=NULL;
    for (size_t i=5;i<fn;i+=src[i]>>16) {
        if ((src[i]&0xffffu)!=NFS_DECORATE || src[i]>>16!=4) continue;
        const uint32_t id=src[i+1],key=src[i+2],v=src[i+3];
        if (id>=bound) goto done;
        if (key==34) {ids[id].set=v;ids[id].flags|=1;}
        if (key==33) {ids[id].binding=v;ids[id].flags|=2;}
        if (key==43) {ids[id].index=v;ids[id].flags|=4;}
    }
    for (uint32_t id=1;id<bound;++id) if (ids[id].flags&4) {
        const uint32_t slot=ids[id].index;
        if (ids[id].flags!=7 || ids[id].set!=3 || slot>=8 || ids[id].binding!=192+slot) goto done;
        if (available&(1u<<slot)) *live|=1u<<slot;
        else {ids[id].drop=1;missing=1;}
    }
    if (!missing) {rc=0;goto done;}
    for (size_t i=fn;i<words;i+=src[i]>>16) {
        const uint32_t wc=src[i]>>16;
        if ((src[i]&0xffffu)==NFS_LOAD && wc>=4 && src[i+3]<bound && ids[src[i+3]].drop==1) {
            if (!src[i+2] || src[i+2]>=bound || ids[src[i+2]].drop) goto done;
            ids[src[i+2]].drop=2;
        }
    }
    uint32_t next=bound;
    for (size_t i=fn;i<words;i+=src[i]>>16) {
        const uint32_t op=src[i]&0xffffu,wc=src[i]>>16;
        // The targeted load may only feed an image read. An unfamiliar
        // reference (including an ambiguous operand) fails closed.
        for (uint32_t j=1;j<wc;++j) {
            const uint32_t id=src[i+j];
            if (id>=bound || !ids[id].drop) continue;
            if (op==NFS_LOAD && wc>=4 && src[i+3]<bound && ids[src[i+3]].drop==1 && (j==2 || j==3)) continue;
            if (op==NFS_READ && wc>=5 && j==3 && ids[id].drop==2) {
                const uint32_t type=src[i+1];
                if (!type || type>=bound) goto done;
                if (!ids[type].zero) ids[type].zero=next++;
                continue;
            }
            goto done;
        }
    }
    const size_t constants=(size_t)next-bound;
    if (words>SIZE_MAX/sizeof(uint32_t)-3*constants) goto done;
    dst=(uint32_t *)malloc((words+3*constants)*sizeof(uint32_t));
    if (!dst) goto done;
    memcpy(dst,src,5*sizeof(uint32_t));dst[3]=next;size_t n=5;
    for (size_t i=5;i<words;i+=src[i]>>16) {
        const uint32_t op=src[i]&0xffffu,wc=src[i]>>16;
        if (i==fn) for (uint32_t t=1;t<bound;++t) if (ids[t].zero) {
            dst[n++]=(3u<<16)|NFS_NULL;dst[n++]=t;dst[n++]=ids[t].zero;
        }
        if (wc>=2 && (op==NFS_NAME || op==NFS_DECORATE) && src[i+1]<bound && ids[src[i+1]].drop==2) continue;
        if (op==NFS_LOAD && wc>=4 && src[i+2]<bound && ids[src[i+2]].drop==2) continue;
        if (op==NFS_READ && wc>=5 && src[i+3]<bound && ids[src[i+3]].drop==2) {
            dst[n++]=(4u<<16)|NFS_COPY;dst[n++]=src[i+1];dst[n++]=src[i+2];dst[n++]=ids[src[i+1]].zero;
        } else {memcpy(dst+n,src+i,(size_t)wc*sizeof(uint32_t));n+=wc;}
    }
    *output=dst;*output_words=n;dst=NULL;rc=0;
done:
    free(dst);free(ids);return rc;
}
#endif
