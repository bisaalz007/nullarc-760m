/* SPDX-License-Identifier: MIT
 * Load the RADV ICD directly: mock inspection and ACO compilation only.
 * No Vulkan loader installation and no physical GPU connection required.
 */
#include <vulkan/vulkan.h>
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
int main(int argc, char **argv) {
    assert((argc == 4 || argc == 5 || argc == 7) && getenv("RADV_DARWIN_MOCK") && !strcmp(getenv("RADV_DARWIN_MOCK"), "1"));
    unsigned expected = (unsigned)atoi(argv[2]);
    void *lib = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "%s\n", dlerror()); return 1; }
    PFN_vkGetInstanceProcAddr gpa = (PFN_vkGetInstanceProcAddr)dlsym(lib, "vk_icdGetInstanceProcAddr");
    assert(gpa);
    PFN_vkCreateInstance create = (PFN_vkCreateInstance)gpa(NULL, "vkCreateInstance");
    const VkApplicationInfo app = {.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion=VK_API_VERSION_1_3};
    const VkInstanceCreateInfo ci = {.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo=&app};
    VkInstance instance; assert(create(&ci, NULL, &instance) == VK_SUCCESS);
    PFN_vkEnumeratePhysicalDevices enumerate = (PFN_vkEnumeratePhysicalDevices)gpa(instance, "vkEnumeratePhysicalDevices");
    PFN_vkGetPhysicalDeviceProperties2 properties = (PFN_vkGetPhysicalDeviceProperties2)gpa(instance, "vkGetPhysicalDeviceProperties2");
    PFN_vkDestroyInstance destroy = (PFN_vkDestroyInstance)gpa(instance, "vkDestroyInstance");
    uint32_t count=1; VkPhysicalDevice device;
    assert(enumerate(instance, &count, &device) == VK_SUCCESS && count == 1);
    VkPhysicalDevicePCIBusInfoPropertiesEXT pci = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PCI_BUS_INFO_PROPERTIES_EXT};
    VkPhysicalDeviceShaderCoreProperties2AMD core2 = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_CORE_PROPERTIES_2_AMD, .pNext=&pci};
    VkPhysicalDeviceShaderCorePropertiesAMD core = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SHADER_CORE_PROPERTIES_AMD, .pNext=&core2};
    VkPhysicalDeviceProperties2 p = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext=&core};
    properties(device, &p);
    assert(p.properties.vendorID == 0x1002 && p.properties.deviceID == 0x1900);
    assert(core2.activeComputeUnitCount == expected);
    assert(core.shaderEngineCount == 1 && core.shaderArraysPerEngineCount == 2);
    assert(strstr(p.properties.deviceName, expected == 8 ? "760M" : "780M"));
    if (expected == 8) assert(p.properties.limits.timestampPeriod == 10.0f);
    else assert(p.properties.limits.timestampPeriod > 10.01f && p.properties.limits.timestampPeriod < 10.03f);
    printf("[PASS] %s: %u CUs, SE=%u SA=%u CU/SA=%u (mock, no execution)\n", p.properties.deviceName,
           core2.activeComputeUnitCount, core.shaderEngineCount, core.shaderArraysPerEngineCount, core.computeUnitsPerShaderArray);
    // Compile a real storage-buffer shader using RADV/ACO, without dispatching.
    PFN_vkCreateDevice create_device = (PFN_vkCreateDevice)gpa(instance, "vkCreateDevice");
    PFN_vkGetDeviceProcAddr dgpa = (PFN_vkGetDeviceProcAddr)gpa(instance, "vkGetDeviceProcAddr");
    float priority = 1;
    VkDeviceQueueCreateInfo qi = {.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO, .queueFamilyIndex=0, .queueCount=1, .pQueuePriorities=&priority};
    VkPhysicalDeviceVulkan13Features features = {.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_3_FEATURES, .dynamicRendering=VK_TRUE};
    VkDeviceCreateInfo di = {.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .pNext=&features, .queueCreateInfoCount=1, .pQueueCreateInfos=&qi};
    VkDevice logical; assert(create_device(device, &di, NULL, &logical) == VK_SUCCESS);
    #define FN(type, name) type name = (type)dgpa(logical, #name)
    FN(PFN_vkCreateShaderModule, vkCreateShaderModule);
    FN(PFN_vkCreateDescriptorSetLayout, vkCreateDescriptorSetLayout);
    FN(PFN_vkCreatePipelineLayout, vkCreatePipelineLayout);
    FN(PFN_vkCreateComputePipelines, vkCreateComputePipelines);
    FN(PFN_vkDestroyPipeline, vkDestroyPipeline);
    FN(PFN_vkDestroyPipelineLayout, vkDestroyPipelineLayout);
    FN(PFN_vkDestroyDescriptorSetLayout, vkDestroyDescriptorSetLayout);
    FN(PFN_vkDestroyShaderModule, vkDestroyShaderModule);
    FN(PFN_vkDestroyDevice, vkDestroyDevice);
    #undef FN
    FILE *f = fopen(argv[3], "rb"); assert(f);
    assert(!fseek(f, 0, SEEK_END)); long bytes = ftell(f); assert(bytes > 0 && !(bytes % 4));
    rewind(f); uint32_t *code = malloc((size_t)bytes); assert(code);
    assert(fread(code, (size_t)bytes, 1, f) == 1); fclose(f);
    assert((size_t)bytes >= 20 && code[0] == 0x07230203);
    const char *entry = argc >= 5 ? argv[4] : "main";
    int entry_found = 0;
    for (size_t i = 5; i < (size_t)bytes / 4;) {
        const uint32_t wc = code[i] >> 16;
        assert(wc && i + wc <= (size_t)bytes / 4);
        if ((code[i] & 0xffff) == 15 && wc >= 4 && code[i+1] == 5) {
            const char *name = (const char *)&code[i+3];
            assert(memchr(name, 0, (wc - 3) * 4));
            if (!strcmp(name, entry)) entry_found = 1;
        }
        i += wc;
    }
    assert(entry_found && "requested compute entry must exist in the SPIR-V");
    VkShaderModuleCreateInfo mi = {.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize=(size_t)bytes, .pCode=code};
    VkShaderModule module; assert(vkCreateShaderModule(logical, &mi, NULL, &module) == VK_SUCCESS); free(code);
    VkDescriptorSetLayoutBinding binding = {.binding=0, .descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount=1, .stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};
    VkDescriptorSetLayoutCreateInfo si = {.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO, .bindingCount=1, .pBindings=&binding};
    VkDescriptorSetLayout set; assert(vkCreateDescriptorSetLayout(logical, &si, NULL, &set) == VK_SUCCESS);
    VkPipelineLayoutCreateInfo li = {.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount=1, .pSetLayouts=&set};
    VkPipelineLayout layout; assert(vkCreatePipelineLayout(logical, &li, NULL, &layout) == VK_SUCCESS);
    VkComputePipelineCreateInfo pi = {.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
        .stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage=VK_SHADER_STAGE_COMPUTE_BIT, .module=module, .pName=entry}, .layout=layout};
    VkPipeline pipeline; assert(vkCreateComputePipelines(logical, VK_NULL_HANDLE, 1, &pi, NULL, &pipeline) == VK_SUCCESS);
    puts("[PASS] gfx1103 ACO compute pipeline compiled; no commands submitted");
    vkDestroyPipeline(logical, pipeline, NULL); vkDestroyPipelineLayout(logical, layout, NULL);
    vkDestroyDescriptorSetLayout(logical, set, NULL); vkDestroyShaderModule(logical, module, NULL);
    if (argc == 7) {
        PFN_vkCreateGraphicsPipelines vkCreateGraphicsPipelines = (PFN_vkCreateGraphicsPipelines)dgpa(logical, "vkCreateGraphicsPipelines");
        VkShaderModule modules[2];
        for (unsigned s = 0; s < 2; ++s) {
            FILE *shader = fopen(argv[5+s], "rb"); assert(shader);
            assert(!fseek(shader, 0, SEEK_END)); long size = ftell(shader); assert(size >= 20 && !(size % 4));
            rewind(shader); uint32_t *words = malloc((size_t)size); assert(words);
            assert(fread(words,(size_t)size,1,shader) == 1); fclose(shader);
            VkShaderModuleCreateInfo info = {.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize=(size_t)size, .pCode=words};
            assert(vkCreateShaderModule(logical,&info,NULL,&modules[s]) == VK_SUCCESS); free(words);
        }
        VkPipelineLayoutCreateInfo empty = {.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO};
        VkPipelineLayout graphics_layout; assert(vkCreatePipelineLayout(logical,&empty,NULL,&graphics_layout) == VK_SUCCESS);
        VkPipelineShaderStageCreateInfo stages[2] = {
            {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_VERTEX_BIT,.module=modules[0],.pName="main"},
            {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=modules[1],.pName="main"}};
        VkFormat format = VK_FORMAT_R8G8B8A8_UNORM;
        VkPipelineRenderingCreateInfo rendering = {.sType=VK_STRUCTURE_TYPE_PIPELINE_RENDERING_CREATE_INFO,.colorAttachmentCount=1,.pColorAttachmentFormats=&format};
        VkPipelineVertexInputStateCreateInfo vertex = {.sType=VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO};
        VkPipelineInputAssemblyStateCreateInfo assembly = {.sType=VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,.topology=VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST};
        VkPipelineViewportStateCreateInfo viewport = {.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.scissorCount=1};
        VkPipelineRasterizationStateCreateInfo raster = {.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.lineWidth=1};
        VkPipelineMultisampleStateCreateInfo ms = {.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
        VkPipelineColorBlendAttachmentState attachment = {.colorWriteMask=VK_COLOR_COMPONENT_R_BIT|VK_COLOR_COMPONENT_G_BIT|VK_COLOR_COMPONENT_B_BIT|VK_COLOR_COMPONENT_A_BIT};
        VkPipelineColorBlendStateCreateInfo blend = {.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&attachment};
        VkDynamicState dynamic_states[] = {VK_DYNAMIC_STATE_VIEWPORT,VK_DYNAMIC_STATE_SCISSOR};
        VkPipelineDynamicStateCreateInfo dynamic = {.sType=VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,.dynamicStateCount=2,.pDynamicStates=dynamic_states};
        VkGraphicsPipelineCreateInfo graphics = {.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.pNext=&rendering,
            .stageCount=2,.pStages=stages,.pVertexInputState=&vertex,.pInputAssemblyState=&assembly,.pViewportState=&viewport,
            .pRasterizationState=&raster,.pMultisampleState=&ms,.pColorBlendState=&blend,.pDynamicState=&dynamic,.layout=graphics_layout};
        VkPipeline graphics_pipeline; assert(vkCreateGraphicsPipelines(logical,VK_NULL_HANDLE,1,&graphics,NULL,&graphics_pipeline) == VK_SUCCESS);
        vkDestroyPipeline(logical,graphics_pipeline,NULL); vkDestroyPipelineLayout(logical,graphics_layout,NULL);
        for (unsigned s = 0; s < 2; ++s) vkDestroyShaderModule(logical,modules[s],NULL);
        puts("[PASS] translated vertex/fragment gfx1103 graphics pipeline compiled; no draw submitted");
    }
    vkDestroyDevice(logical, NULL);
    destroy(instance, NULL); dlclose(lib);
}
