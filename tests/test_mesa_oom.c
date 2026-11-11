/* SPDX-License-Identifier: MIT
 * Exhaust the mock native client's BO handles, then allocate a command buffer.
 * A failed command stream must return OOM through the normal Vulkan API.
 */
#include <vulkan/vulkan.h>
#include <assert.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    assert(argc == 2 && getenv("RADV_DARWIN_MOCK") && !strcmp(getenv("RADV_DARWIN_MOCK"), "1"));
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
    assert(library);
    PFN_vkGetInstanceProcAddr instance_proc = dlsym(library, "vk_icdGetInstanceProcAddr");
    assert(instance_proc);
    PFN_vkCreateInstance create_instance = (PFN_vkCreateInstance)instance_proc(NULL, "vkCreateInstance");
    VkInstanceCreateInfo instance_info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};
    VkInstance instance;
    assert(create_instance(&instance_info, NULL, &instance) == VK_SUCCESS);
#define INSTANCE_FN(name) PFN_##name name = (PFN_##name)instance_proc(instance, #name)
    INSTANCE_FN(vkEnumeratePhysicalDevices);
    INSTANCE_FN(vkGetPhysicalDeviceMemoryProperties);
    INSTANCE_FN(vkCreateDevice);
    INSTANCE_FN(vkGetDeviceProcAddr);
    INSTANCE_FN(vkDestroyInstance);
#undef INSTANCE_FN
    uint32_t count = 1;
    VkPhysicalDevice physical;
    assert(vkEnumeratePhysicalDevices(instance, &count, &physical) == VK_SUCCESS && count == 1);
    VkPhysicalDeviceMemoryProperties properties;
    vkGetPhysicalDeviceMemoryProperties(physical, &properties);
    uint32_t type = 0;
    while (type < properties.memoryTypeCount) {
        VkMemoryPropertyFlags flags = properties.memoryTypes[type].propertyFlags;
        if ((flags & VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT) && !(flags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)) break;
        type++;
    }
    assert(type < properties.memoryTypeCount);
    float priority = 1;
    VkDeviceQueueCreateInfo queue = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = 0, .queueCount = 1, .pQueuePriorities = &priority};
    VkDeviceCreateInfo device_info = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue};
    VkDevice device;
    assert(vkCreateDevice(physical, &device_info, NULL, &device) == VK_SUCCESS);
#define DEVICE_FN(name) PFN_##name name = (PFN_##name)vkGetDeviceProcAddr(device, #name)
    DEVICE_FN(vkAllocateMemory);
    DEVICE_FN(vkFreeMemory);
    DEVICE_FN(vkCreateCommandPool);
    DEVICE_FN(vkAllocateCommandBuffers);
    DEVICE_FN(vkDestroyCommandPool);
    DEVICE_FN(vkDestroyDevice);
#undef DEVICE_FN
    VkCommandPoolCreateInfo pool_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = 0};
    VkCommandPool pool;
    assert(vkCreateCommandPool(device, &pool_info, NULL, &pool) == VK_SUCCESS);
    VkDeviceMemory allocations[4096];
    VkMemoryAllocateInfo memory = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = 4096, .memoryTypeIndex = type};
    uint32_t allocated = 0;
    VkResult result = VK_SUCCESS;
    while (allocated < 4096) {
        result = vkAllocateMemory(device, &memory, NULL, &allocations[allocated]);
        if (result != VK_SUCCESS) break;
        allocated++;
    }
    assert(allocated && allocated < 4096 && result == VK_ERROR_OUT_OF_DEVICE_MEMORY);
    VkCommandBufferAllocateInfo command_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    VkCommandBuffer command;
    result = vkAllocateCommandBuffers(device, &command_info, &command);
    assert(result == VK_ERROR_OUT_OF_DEVICE_MEMORY);
    vkDestroyCommandPool(device, pool, NULL);
    for (uint32_t i = 0; i < allocated; i++) vkFreeMemory(device, allocations[i], NULL);
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    dlclose(library);
    puts("[PASS] command-buffer allocation returns OOM after native BO exhaustion (mock, no submissions)");
}
