/* SPDX-License-Identifier: MIT
 * Execute this project's translated triangle_vertex/solid_fragment fixtures.
 * Offscreen only: no display takeover. Requires AMD 1002:1900 and Mesa RADV.
 * Linux success is not evidence of the macOS kernel/winsys execution path.
 */
#include <vulkan/vulkan.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define CHECK(expr) do { VkResult r = (expr); if (r != VK_SUCCESS) { \
    fprintf(stderr, "%s: VkResult %d\n", #expr, r); return 1; } } while (0)
#define NEED(expr) do { if (!(expr)) { fprintf(stderr, "failed: %s\n", #expr); return 1; } } while (0)

static VkShaderModule shader(VkDevice dev, const char *path) {
    FILE *f = fopen(path,"rb");
    if (!f) return VK_NULL_HANDLE;
    if (fseek(f,0,SEEK_END)) { fclose(f); return VK_NULL_HANDLE; }
    long bytes=ftell(f);
    if (bytes<20 || bytes>16*1024*1024 || bytes%4 || fseek(f,0,SEEK_SET)) { fclose(f); return VK_NULL_HANDLE; }
    uint32_t *code=malloc((size_t)bytes);
    if (!code) { fclose(f); return VK_NULL_HANDLE; }
    VkShaderModule module=VK_NULL_HANDLE;
    if (fread(code,(size_t)bytes,1,f)==1 && code[0]==0x07230203) {
        VkShaderModuleCreateInfo ci={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=(size_t)bytes,.pCode=code};
        if (vkCreateShaderModule(dev,&ci,NULL,&module)!=VK_SUCCESS) module=VK_NULL_HANDLE;
    }
    free(code); fclose(f); return module;
}
static uint32_t memory_type(VkPhysicalDevice pd, uint32_t bits, VkMemoryPropertyFlags flags) {
    VkPhysicalDeviceMemoryProperties mp; vkGetPhysicalDeviceMemoryProperties(pd,&mp);
    for (uint32_t i=0;i<mp.memoryTypeCount;++i)
        if ((bits&(1u<<i)) && (mp.memoryTypes[i].propertyFlags&flags)==flags) return i;
    return UINT32_MAX;
}

int main(int argc,char **argv) {
    NEED(argc==3);
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="NullArc translated fixture",
                          .apiVersion=VK_API_VERSION_1_3};
    VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};
    VkInstance instance; CHECK(vkCreateInstance(&ici,NULL,&instance));
    uint32_t count=0; CHECK(vkEnumeratePhysicalDevices(instance,&count,NULL)); NEED(count && count<=32);
    VkPhysicalDevice devices[32]; CHECK(vkEnumeratePhysicalDevices(instance,&count,devices));
    VkPhysicalDevice pd=VK_NULL_HANDLE;
    for (uint32_t i=0;i<count;++i) {
        VkPhysicalDeviceDriverProperties driver={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
        VkPhysicalDeviceProperties2 p={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&driver};
        vkGetPhysicalDeviceProperties2(devices[i],&p);
        if (p.properties.vendorID==0x1002 && p.properties.deviceID==0x1900 &&
            p.properties.deviceType==VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU && driver.driverID==VK_DRIVER_ID_MESA_RADV) {
            pd=devices[i]; printf("selected %s (%s)\n",p.properties.deviceName,driver.driverInfo); break;
        }
    }
    NEED(pd!=VK_NULL_HANDLE);
    uint32_t qn=0; vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,NULL); NEED(qn && qn<=32);
    VkQueueFamilyProperties qf[32]; vkGetPhysicalDeviceQueueFamilyProperties(pd,&qn,qf);
    uint32_t family=UINT32_MAX;
    for (uint32_t i=0;i<qn;++i) if (qf[i].queueCount && (qf[i].queueFlags&VK_QUEUE_GRAPHICS_BIT)) { family=i; break; }
    NEED(family!=UINT32_MAX);
    VkPhysicalDeviceVulkan13Features available={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES};
    VkPhysicalDeviceFeatures2 features={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,.pNext=&available};
    vkGetPhysicalDeviceFeatures2(pd,&features); NEED(available.dynamicRendering);
    VkPhysicalDeviceVulkan13Features enabled={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES,.dynamicRendering=VK_TRUE};
    float priority=1;
    VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};
    VkDeviceCreateInfo dci={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.pNext=&enabled,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi};
    VkDevice dev; CHECK(vkCreateDevice(pd,&dci,NULL,&dev));
    VkQueue queue; vkGetDeviceQueue(dev,family,0,&queue);
    enum { W=16,H=16,BYTES=W*H*4 };
    const VkFormat format=VK_FORMAT_R8G8B8A8_UNORM;
    VkFormatProperties fp; vkGetPhysicalDeviceFormatProperties(pd,format,&fp);
    NEED((fp.optimalTilingFeatures&(VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT|VK_FORMAT_FEATURE_TRANSFER_SRC_BIT))==
         (VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT|VK_FORMAT_FEATURE_TRANSFER_SRC_BIT));
    VkImageCreateInfo image_ci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=format,
        .extent={W,H,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,
        .usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT};
    VkImage image; CHECK(vkCreateImage(dev,&image_ci,NULL,&image));
    VkMemoryRequirements mr; vkGetImageMemoryRequirements(dev,image,&mr);
    uint32_t type=memory_type(pd,mr.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT); NEED(type!=UINT32_MAX);
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=mr.size,.memoryTypeIndex=type};
    VkDeviceMemory image_mem; CHECK(vkAllocateMemory(dev,&ai,NULL,&image_mem)); CHECK(vkBindImageMemory(dev,image,image_mem,0));
    VkImageSubresourceRange range={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.levelCount=1,.layerCount=1};
    VkImageViewCreateInfo vi={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=image,.viewType=VK_IMAGE_VIEW_TYPE_2D,
        .format=format,.subresourceRange=range};
    VkImageView view; CHECK(vkCreateImageView(dev,&vi,NULL,&view));
    VkBufferCreateInfo bi={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=BYTES,.usage=VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    VkBuffer buffer; CHECK(vkCreateBuffer(dev,&bi,NULL,&buffer)); vkGetBufferMemoryRequirements(dev,buffer,&mr);
    type=memory_type(pd,mr.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT); NEED(type!=UINT32_MAX);
    ai.allocationSize=mr.size; ai.memoryTypeIndex=type;
    VkDeviceMemory host_mem; CHECK(vkAllocateMemory(dev,&ai,NULL,&host_mem)); CHECK(vkBindBufferMemory(dev,buffer,host_mem,0));
    uint8_t *pixels; CHECK(vkMapMemory(dev,host_mem,0,VK_WHOLE_SIZE,0,(void**)&pixels));
    for (unsigned i=0;i<BYTES;++i) pixels[i]=0xab;
    VkShaderModule vertex=shader(dev,argv[1]),fragment=shader(dev,argv[2]); NEED(vertex && fragment);
    VkPipelineShaderStageCreateInfo stages[]={
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=vertex,.pName="main"},
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=fragment,.pName="main"}};
    VkPipelineVertexInputStateCreateInfo vertices={.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
    VkPipelineInputAssemblyStateCreateInfo assembly={.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
    VkViewport viewport={.width=W,.height=H,.maxDepth=1}; VkRect2D area={.extent={W,H}};
    VkPipelineViewportStateCreateInfo vp={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&viewport,.scissorCount=1,.pScissors=&area};
    VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.lineWidth=1};
    VkPipelineMultisampleStateCreateInfo samples={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
    VkPipelineColorBlendAttachmentState attachment={.colorWriteMask=0xf};
    VkPipelineColorBlendStateCreateInfo blend={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&attachment};
    VkPipelineLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
    VkPipelineLayout layout; CHECK(vkCreatePipelineLayout(dev,&li,NULL,&layout));
    VkPipelineRenderingCreateInfo rendering={.sType=VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,.colorAttachmentCount=1,.pColorAttachmentFormats=&format};
    VkGraphicsPipelineCreateInfo pi={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.pNext=&rendering,.stageCount=2,.pStages=stages,
        .pVertexInputState=&vertices,.pInputAssemblyState=&assembly,.pViewportState=&vp,.pRasterizationState=&raster,
        .pMultisampleState=&samples,.pColorBlendState=&blend,.layout=layout};
    VkPipeline pipeline; CHECK(vkCreateGraphicsPipelines(dev,VK_NULL_HANDLE,1,&pi,NULL,&pipeline));
    VkCommandPoolCreateInfo pool_ci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=family};
    VkCommandPool pool; CHECK(vkCreateCommandPool(dev,&pool_ci,NULL,&pool));
    VkCommandBufferAllocateInfo cba={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};
    VkCommandBuffer cb; CHECK(vkAllocateCommandBuffers(dev,&cba,&cb));
    VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO}; CHECK(vkBeginCommandBuffer(cb,&begin));
    VkImageMemoryBarrier image_barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,
        .newLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,.dstAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
        .srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=image,.subresourceRange=range};
    vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,0,0,NULL,0,NULL,1,&image_barrier);
    VkRenderingAttachmentInfo color={.sType=VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO,.imageView=view,
        .imageLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE};
    VkRenderingInfo ri={.sType=VK_STRUCTURE_TYPE_RENDERING_INFO,.renderArea=area,.layerCount=1,.colorAttachmentCount=1,.pColorAttachments=&color};
    vkCmdBeginRendering(cb,&ri); vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,pipeline); vkCmdDraw(cb,3,1,0,0); vkCmdEndRendering(cb);
    image_barrier.oldLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL; image_barrier.newLayout=VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
    image_barrier.srcAccessMask=VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT; image_barrier.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
    vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&image_barrier);
    VkBufferImageCopy region={.imageSubresource={.aspectMask=VK_IMAGE_ASPECT_COLOR_BIT,.layerCount=1},.imageExtent={W,H,1}};
    vkCmdCopyImageToBuffer(cb,image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,buffer,1,&region);
    VkMemoryBarrier host={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&host,0,NULL,0,NULL);
    CHECK(vkEndCommandBuffer(cb));
    VkFenceCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO}; VkFence fence; CHECK(vkCreateFence(dev,&fi,NULL,&fence));
    VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cb};
    CHECK(vkQueueSubmit(queue,1,&submit,fence)); CHECK(vkWaitForFences(dev,1,&fence,VK_TRUE,2000000000ull));
    unsigned good=0;
    for (unsigned i=0;i<W*H;++i) {
        // UNORM conversion permits a one-unit rounding difference at half steps.
        const uint8_t *p=pixels+i*4;
        good += abs((int)p[0]-64)<=1 && abs((int)p[1]-128)<=1 && abs((int)p[2]-191)<=1 && p[3]==255;
    }
    printf("translated MSL draw + fence + image readback: %u/%u pixels; first RGBA=%u,%u,%u,%u\n",good,W*H,pixels[0],pixels[1],pixels[2],pixels[3]);
    vkDestroyFence(dev,fence,NULL); vkDestroyCommandPool(dev,pool,NULL); vkDestroyPipeline(dev,pipeline,NULL);
    vkDestroyPipelineLayout(dev,layout,NULL); vkDestroyShaderModule(dev,vertex,NULL); vkDestroyShaderModule(dev,fragment,NULL);
    vkDestroyImageView(dev,view,NULL); vkDestroyImage(dev,image,NULL); vkFreeMemory(dev,image_mem,NULL);
    vkUnmapMemory(dev,host_mem); vkDestroyBuffer(dev,buffer,NULL); vkFreeMemory(dev,host_mem,NULL);
    vkDestroyDevice(dev,NULL); vkDestroyInstance(instance,NULL);
    return good==W*H ? 0 : 1;
}
