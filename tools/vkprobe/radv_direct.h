/* SPDX-License-Identifier: MIT
 * Direct RADV ICD dispatch for native probes, without a system Vulkan loader.
 * All entry points come from the explicitly selected driver. Mocks are refused.
 */
#ifndef PHX_RADV_DIRECT_H
#define PHX_RADV_DIRECT_H
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
static PFN_vkAllocateCommandBuffers vkAllocateCommandBuffers;
static PFN_vkAllocateDescriptorSets vkAllocateDescriptorSets;
static PFN_vkAllocateMemory vkAllocateMemory;
static PFN_vkBeginCommandBuffer vkBeginCommandBuffer;
static PFN_vkBindBufferMemory vkBindBufferMemory;
static PFN_vkBindImageMemory vkBindImageMemory;
static PFN_vkCmdBeginRendering vkCmdBeginRendering;
static PFN_vkCmdBindDescriptorSets vkCmdBindDescriptorSets;
static PFN_vkCmdBindPipeline vkCmdBindPipeline;
static PFN_vkCmdCopyImageToBuffer vkCmdCopyImageToBuffer;
static PFN_vkCmdDispatch vkCmdDispatch;
static PFN_vkCmdDraw vkCmdDraw;
static PFN_vkCmdEndRendering vkCmdEndRendering;
static PFN_vkCmdPipelineBarrier vkCmdPipelineBarrier;
static PFN_vkCreateBuffer vkCreateBuffer;
static PFN_vkCreateCommandPool vkCreateCommandPool;
static PFN_vkCreateComputePipelines vkCreateComputePipelines;
static PFN_vkCreateDescriptorPool vkCreateDescriptorPool;
static PFN_vkCreateDescriptorSetLayout vkCreateDescriptorSetLayout;
static PFN_vkCreateDevice vkCreateDevice;
static PFN_vkCreateFence vkCreateFence;
static PFN_vkCreateGraphicsPipelines vkCreateGraphicsPipelines;
static PFN_vkCreateImage vkCreateImage;
static PFN_vkCreateImageView vkCreateImageView;
static PFN_vkCreatePipelineLayout vkCreatePipelineLayout;
static PFN_vkCreateShaderModule vkCreateShaderModule;
static PFN_vkDestroyBuffer vkDestroyBuffer;
static PFN_vkDestroyCommandPool vkDestroyCommandPool;
static PFN_vkDestroyDescriptorPool vkDestroyDescriptorPool;
static PFN_vkDestroyDescriptorSetLayout vkDestroyDescriptorSetLayout;
static PFN_vkDestroyDevice vkDestroyDevice;
static PFN_vkDestroyFence vkDestroyFence;
static PFN_vkDestroyImage vkDestroyImage;
static PFN_vkDestroyImageView vkDestroyImageView;
static PFN_vkDestroyInstance vkDestroyInstance;
static PFN_vkDestroyPipeline vkDestroyPipeline;
static PFN_vkDestroyPipelineLayout vkDestroyPipelineLayout;
static PFN_vkDestroyShaderModule vkDestroyShaderModule;
static PFN_vkEndCommandBuffer vkEndCommandBuffer;
static PFN_vkEnumeratePhysicalDevices vkEnumeratePhysicalDevices;
static PFN_vkFreeMemory vkFreeMemory;
static PFN_vkGetBufferMemoryRequirements vkGetBufferMemoryRequirements;
static PFN_vkGetDeviceQueue vkGetDeviceQueue;
static PFN_vkGetImageMemoryRequirements vkGetImageMemoryRequirements;
static PFN_vkGetPhysicalDeviceFeatures2 vkGetPhysicalDeviceFeatures2;
static PFN_vkGetPhysicalDeviceFormatProperties vkGetPhysicalDeviceFormatProperties;
static PFN_vkGetPhysicalDeviceMemoryProperties vkGetPhysicalDeviceMemoryProperties;
static PFN_vkGetPhysicalDeviceProperties2 vkGetPhysicalDeviceProperties2;
static PFN_vkGetPhysicalDeviceQueueFamilyProperties vkGetPhysicalDeviceQueueFamilyProperties;
static PFN_vkMapMemory vkMapMemory;
static PFN_vkQueueSubmit vkQueueSubmit;
static PFN_vkUnmapMemory vkUnmapMemory;
static PFN_vkUpdateDescriptorSets vkUpdateDescriptorSets;
static PFN_vkWaitForFences vkWaitForFences;
static VkResult phxDirectCreateInstance(const VkInstanceCreateInfo *info,const VkAllocationCallbacks *alloc,VkInstance *instance) {
    const char *path=getenv("PHX_RADV_DRIVER");
    if (!path || *path!='/' || getenv("RADV_DARWIN_MOCK") || getenv("RADV_DARWIN_MOCK_HP")) {
        fprintf(stderr,"native probe requires absolute PHX_RADV_DRIVER and refuses mock transport\n");return VK_ERROR_INITIALIZATION_FAILED;
    }
    void *library=dlopen(path,RTLD_NOW|RTLD_LOCAL);
    if (!library) { fprintf(stderr,"RADV dlopen: %s\n",dlerror());return VK_ERROR_INITIALIZATION_FAILED; }
    PFN_vkGetInstanceProcAddr gpa=(PFN_vkGetInstanceProcAddr)dlsym(library,"vk_icdGetInstanceProcAddr");
    if (!gpa) return VK_ERROR_INITIALIZATION_FAILED;
    PFN_vkCreateInstance create=(PFN_vkCreateInstance)gpa(VK_NULL_HANDLE,"vkCreateInstance");
    if (!create) return VK_ERROR_INITIALIZATION_FAILED;
    const VkResult result=create(info,alloc,instance);
    if (result!=VK_SUCCESS) return result;
    vkAllocateCommandBuffers=(PFN_vkAllocateCommandBuffers)gpa(*instance,"vkAllocateCommandBuffers");
    vkAllocateDescriptorSets=(PFN_vkAllocateDescriptorSets)gpa(*instance,"vkAllocateDescriptorSets");
    vkAllocateMemory=(PFN_vkAllocateMemory)gpa(*instance,"vkAllocateMemory");
    vkBeginCommandBuffer=(PFN_vkBeginCommandBuffer)gpa(*instance,"vkBeginCommandBuffer");
    vkBindBufferMemory=(PFN_vkBindBufferMemory)gpa(*instance,"vkBindBufferMemory");
    vkBindImageMemory=(PFN_vkBindImageMemory)gpa(*instance,"vkBindImageMemory");
    vkCmdBeginRendering=(PFN_vkCmdBeginRendering)gpa(*instance,"vkCmdBeginRendering");
    vkCmdBindDescriptorSets=(PFN_vkCmdBindDescriptorSets)gpa(*instance,"vkCmdBindDescriptorSets");
    vkCmdBindPipeline=(PFN_vkCmdBindPipeline)gpa(*instance,"vkCmdBindPipeline");
    vkCmdCopyImageToBuffer=(PFN_vkCmdCopyImageToBuffer)gpa(*instance,"vkCmdCopyImageToBuffer");
    vkCmdDispatch=(PFN_vkCmdDispatch)gpa(*instance,"vkCmdDispatch");
    vkCmdDraw=(PFN_vkCmdDraw)gpa(*instance,"vkCmdDraw");
    vkCmdEndRendering=(PFN_vkCmdEndRendering)gpa(*instance,"vkCmdEndRendering");
    vkCmdPipelineBarrier=(PFN_vkCmdPipelineBarrier)gpa(*instance,"vkCmdPipelineBarrier");
    vkCreateBuffer=(PFN_vkCreateBuffer)gpa(*instance,"vkCreateBuffer");
    vkCreateCommandPool=(PFN_vkCreateCommandPool)gpa(*instance,"vkCreateCommandPool");
    vkCreateComputePipelines=(PFN_vkCreateComputePipelines)gpa(*instance,"vkCreateComputePipelines");
    vkCreateDescriptorPool=(PFN_vkCreateDescriptorPool)gpa(*instance,"vkCreateDescriptorPool");
    vkCreateDescriptorSetLayout=(PFN_vkCreateDescriptorSetLayout)gpa(*instance,"vkCreateDescriptorSetLayout");
    vkCreateDevice=(PFN_vkCreateDevice)gpa(*instance,"vkCreateDevice");
    vkCreateFence=(PFN_vkCreateFence)gpa(*instance,"vkCreateFence");
    vkCreateGraphicsPipelines=(PFN_vkCreateGraphicsPipelines)gpa(*instance,"vkCreateGraphicsPipelines");
    vkCreateImage=(PFN_vkCreateImage)gpa(*instance,"vkCreateImage");
    vkCreateImageView=(PFN_vkCreateImageView)gpa(*instance,"vkCreateImageView");
    vkCreatePipelineLayout=(PFN_vkCreatePipelineLayout)gpa(*instance,"vkCreatePipelineLayout");
    vkCreateShaderModule=(PFN_vkCreateShaderModule)gpa(*instance,"vkCreateShaderModule");
    vkDestroyBuffer=(PFN_vkDestroyBuffer)gpa(*instance,"vkDestroyBuffer");
    vkDestroyCommandPool=(PFN_vkDestroyCommandPool)gpa(*instance,"vkDestroyCommandPool");
    vkDestroyDescriptorPool=(PFN_vkDestroyDescriptorPool)gpa(*instance,"vkDestroyDescriptorPool");
    vkDestroyDescriptorSetLayout=(PFN_vkDestroyDescriptorSetLayout)gpa(*instance,"vkDestroyDescriptorSetLayout");
    vkDestroyDevice=(PFN_vkDestroyDevice)gpa(*instance,"vkDestroyDevice");
    vkDestroyFence=(PFN_vkDestroyFence)gpa(*instance,"vkDestroyFence");
    vkDestroyImage=(PFN_vkDestroyImage)gpa(*instance,"vkDestroyImage");
    vkDestroyImageView=(PFN_vkDestroyImageView)gpa(*instance,"vkDestroyImageView");
    vkDestroyInstance=(PFN_vkDestroyInstance)gpa(*instance,"vkDestroyInstance");
    vkDestroyPipeline=(PFN_vkDestroyPipeline)gpa(*instance,"vkDestroyPipeline");
    vkDestroyPipelineLayout=(PFN_vkDestroyPipelineLayout)gpa(*instance,"vkDestroyPipelineLayout");
    vkDestroyShaderModule=(PFN_vkDestroyShaderModule)gpa(*instance,"vkDestroyShaderModule");
    vkEndCommandBuffer=(PFN_vkEndCommandBuffer)gpa(*instance,"vkEndCommandBuffer");
    vkEnumeratePhysicalDevices=(PFN_vkEnumeratePhysicalDevices)gpa(*instance,"vkEnumeratePhysicalDevices");
    vkFreeMemory=(PFN_vkFreeMemory)gpa(*instance,"vkFreeMemory");
    vkGetBufferMemoryRequirements=(PFN_vkGetBufferMemoryRequirements)gpa(*instance,"vkGetBufferMemoryRequirements");
    vkGetDeviceQueue=(PFN_vkGetDeviceQueue)gpa(*instance,"vkGetDeviceQueue");
    vkGetImageMemoryRequirements=(PFN_vkGetImageMemoryRequirements)gpa(*instance,"vkGetImageMemoryRequirements");
    vkGetPhysicalDeviceFeatures2=(PFN_vkGetPhysicalDeviceFeatures2)gpa(*instance,"vkGetPhysicalDeviceFeatures2");
    vkGetPhysicalDeviceFormatProperties=(PFN_vkGetPhysicalDeviceFormatProperties)gpa(*instance,"vkGetPhysicalDeviceFormatProperties");
    vkGetPhysicalDeviceMemoryProperties=(PFN_vkGetPhysicalDeviceMemoryProperties)gpa(*instance,"vkGetPhysicalDeviceMemoryProperties");
    vkGetPhysicalDeviceProperties2=(PFN_vkGetPhysicalDeviceProperties2)gpa(*instance,"vkGetPhysicalDeviceProperties2");
    vkGetPhysicalDeviceQueueFamilyProperties=(PFN_vkGetPhysicalDeviceQueueFamilyProperties)gpa(*instance,"vkGetPhysicalDeviceQueueFamilyProperties");
    vkMapMemory=(PFN_vkMapMemory)gpa(*instance,"vkMapMemory");
    vkQueueSubmit=(PFN_vkQueueSubmit)gpa(*instance,"vkQueueSubmit");
    vkUnmapMemory=(PFN_vkUnmapMemory)gpa(*instance,"vkUnmapMemory");
    vkUpdateDescriptorSets=(PFN_vkUpdateDescriptorSets)gpa(*instance,"vkUpdateDescriptorSets");
    vkWaitForFences=(PFN_vkWaitForFences)gpa(*instance,"vkWaitForFences");
    if (!vkAllocateCommandBuffers) { fprintf(stderr,"missing RADV vkAllocateCommandBuffers\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkAllocateDescriptorSets) { fprintf(stderr,"missing RADV vkAllocateDescriptorSets\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkAllocateMemory) { fprintf(stderr,"missing RADV vkAllocateMemory\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkBeginCommandBuffer) { fprintf(stderr,"missing RADV vkBeginCommandBuffer\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkBindBufferMemory) { fprintf(stderr,"missing RADV vkBindBufferMemory\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkBindImageMemory) { fprintf(stderr,"missing RADV vkBindImageMemory\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdBeginRendering) { fprintf(stderr,"missing RADV vkCmdBeginRendering\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdBindDescriptorSets) { fprintf(stderr,"missing RADV vkCmdBindDescriptorSets\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdBindPipeline) { fprintf(stderr,"missing RADV vkCmdBindPipeline\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdCopyImageToBuffer) { fprintf(stderr,"missing RADV vkCmdCopyImageToBuffer\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdDispatch) { fprintf(stderr,"missing RADV vkCmdDispatch\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdDraw) { fprintf(stderr,"missing RADV vkCmdDraw\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdEndRendering) { fprintf(stderr,"missing RADV vkCmdEndRendering\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCmdPipelineBarrier) { fprintf(stderr,"missing RADV vkCmdPipelineBarrier\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateBuffer) { fprintf(stderr,"missing RADV vkCreateBuffer\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateCommandPool) { fprintf(stderr,"missing RADV vkCreateCommandPool\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateComputePipelines) { fprintf(stderr,"missing RADV vkCreateComputePipelines\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateDescriptorPool) { fprintf(stderr,"missing RADV vkCreateDescriptorPool\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateDescriptorSetLayout) { fprintf(stderr,"missing RADV vkCreateDescriptorSetLayout\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateDevice) { fprintf(stderr,"missing RADV vkCreateDevice\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateFence) { fprintf(stderr,"missing RADV vkCreateFence\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateGraphicsPipelines) { fprintf(stderr,"missing RADV vkCreateGraphicsPipelines\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateImage) { fprintf(stderr,"missing RADV vkCreateImage\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateImageView) { fprintf(stderr,"missing RADV vkCreateImageView\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreatePipelineLayout) { fprintf(stderr,"missing RADV vkCreatePipelineLayout\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkCreateShaderModule) { fprintf(stderr,"missing RADV vkCreateShaderModule\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyBuffer) { fprintf(stderr,"missing RADV vkDestroyBuffer\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyCommandPool) { fprintf(stderr,"missing RADV vkDestroyCommandPool\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyDescriptorPool) { fprintf(stderr,"missing RADV vkDestroyDescriptorPool\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyDescriptorSetLayout) { fprintf(stderr,"missing RADV vkDestroyDescriptorSetLayout\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyDevice) { fprintf(stderr,"missing RADV vkDestroyDevice\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyFence) { fprintf(stderr,"missing RADV vkDestroyFence\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyImage) { fprintf(stderr,"missing RADV vkDestroyImage\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyImageView) { fprintf(stderr,"missing RADV vkDestroyImageView\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyInstance) { fprintf(stderr,"missing RADV vkDestroyInstance\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyPipeline) { fprintf(stderr,"missing RADV vkDestroyPipeline\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyPipelineLayout) { fprintf(stderr,"missing RADV vkDestroyPipelineLayout\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkDestroyShaderModule) { fprintf(stderr,"missing RADV vkDestroyShaderModule\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkEndCommandBuffer) { fprintf(stderr,"missing RADV vkEndCommandBuffer\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkEnumeratePhysicalDevices) { fprintf(stderr,"missing RADV vkEnumeratePhysicalDevices\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkFreeMemory) { fprintf(stderr,"missing RADV vkFreeMemory\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetBufferMemoryRequirements) { fprintf(stderr,"missing RADV vkGetBufferMemoryRequirements\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetDeviceQueue) { fprintf(stderr,"missing RADV vkGetDeviceQueue\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetImageMemoryRequirements) { fprintf(stderr,"missing RADV vkGetImageMemoryRequirements\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetPhysicalDeviceFeatures2) { fprintf(stderr,"missing RADV vkGetPhysicalDeviceFeatures2\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetPhysicalDeviceFormatProperties) { fprintf(stderr,"missing RADV vkGetPhysicalDeviceFormatProperties\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetPhysicalDeviceMemoryProperties) { fprintf(stderr,"missing RADV vkGetPhysicalDeviceMemoryProperties\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetPhysicalDeviceProperties2) { fprintf(stderr,"missing RADV vkGetPhysicalDeviceProperties2\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkGetPhysicalDeviceQueueFamilyProperties) { fprintf(stderr,"missing RADV vkGetPhysicalDeviceQueueFamilyProperties\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkMapMemory) { fprintf(stderr,"missing RADV vkMapMemory\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkQueueSubmit) { fprintf(stderr,"missing RADV vkQueueSubmit\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkUnmapMemory) { fprintf(stderr,"missing RADV vkUnmapMemory\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkUpdateDescriptorSets) { fprintf(stderr,"missing RADV vkUpdateDescriptorSets\n");return VK_ERROR_INITIALIZATION_FAILED; }
    if (!vkWaitForFences) { fprintf(stderr,"missing RADV vkWaitForFences\n");return VK_ERROR_INITIALIZATION_FAILED; }
    return VK_SUCCESS;
}
#define vkCreateInstance phxDirectCreateInstance
#endif
