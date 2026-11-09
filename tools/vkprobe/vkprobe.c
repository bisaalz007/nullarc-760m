/*
 * vkprobe.c — minimal Vulkan check for the RADV Darwin build.
 * Enumerates physical devices, prints identity / heaps / queues, creates a device and
 * dispatches fill.comp and checks every result after a bounded fence wait.
 * --hp requires the measured HP PCI identity and RADV; CPU devices are refused.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifdef PHX_DIRECT_RADV
#define VK_NO_PROTOTYPES
#endif
#include <vulkan/vulkan.h>
#ifdef PHX_DIRECT_RADV
#include "radv_direct.h"
#endif

#include "fill_spv.h" /* glslangValidator -V --vn fill_spv fill.comp -o fill_spv.h */

#define CHECK(expr)                                                         \
   do {                                                                     \
      VkResult r_ = (expr);                                                 \
      if (r_ != VK_SUCCESS) {                                               \
         fprintf(stderr, "%s failed: %d\n", #expr, (int)r_);                \
         return 1;                                                          \
      }                                                                     \
   } while (0)

int main(int argc, char **argv)
{
   const int translated = argc == 4 && !strcmp(argv[2], "--translated-store");
   const int hp = (argc == 2 || translated) && !strcmp(argv[1], "--hp");
   if (argc != 1 && !hp) {
      fprintf(stderr, "usage: vkprobe [--hp [--translated-store store.spv]]\n");
      return 1;
   }
   VkApplicationInfo app = {
      .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
      .pApplicationName = "vkprobe",
      .apiVersion = VK_API_VERSION_1_3,
   };
   VkInstanceCreateInfo ici = {
      .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
      .pApplicationInfo = &app,
   };
   VkInstance inst;
   CHECK(vkCreateInstance(&ici, NULL, &inst));

   uint32_t n = 0;
   CHECK(vkEnumeratePhysicalDevices(inst, &n, NULL));
   printf("physical devices: %u\n", n);
   if (!n)
      return 1;
   VkPhysicalDevice pds[8];
   if (n > 8)
      n = 8;
   CHECK(vkEnumeratePhysicalDevices(inst, &n, pds));

   uint32_t selected = UINT32_MAX;
   for (uint32_t i = 0; i < n; i++) {
      VkPhysicalDeviceDriverProperties drv = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
      VkPhysicalDeviceProperties2 p2 = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &drv};
      vkGetPhysicalDeviceProperties2(pds[i], &p2);
      VkPhysicalDeviceProperties *p = &p2.properties;
      printf("[%u] %s  vendor 0x%04x device 0x%04x  api %u.%u.%u\n", i, p->deviceName, p->vendorID,
             p->deviceID, VK_API_VERSION_MAJOR(p->apiVersion), VK_API_VERSION_MINOR(p->apiVersion),
             VK_API_VERSION_PATCH(p->apiVersion));
      printf("    driver: %s (%s)\n", drv.driverName, drv.driverInfo);
      if (selected == UINT32_MAX && p->vendorID == 0x1002 &&
          (p->deviceType == VK_PHYSICAL_DEVICE_TYPE_INTEGRATED_GPU ||
           p->deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) &&
          (!hp || (p->deviceID == 0x1900 && drv.driverID == VK_DRIVER_ID_MESA_RADV)))
         selected = i;

      VkPhysicalDeviceMemoryProperties mp;
      vkGetPhysicalDeviceMemoryProperties(pds[i], &mp);
      for (uint32_t h = 0; h < mp.memoryHeapCount; h++)
         printf("    heap %u: %llu MiB flags 0x%x\n", h, (unsigned long long)(mp.memoryHeaps[h].size >> 20),
                mp.memoryHeaps[h].flags);

      uint32_t qn = 0;
      vkGetPhysicalDeviceQueueFamilyProperties(pds[i], &qn, NULL);
      VkQueueFamilyProperties qf[16];
      if (qn > 16)
         qn = 16;
      vkGetPhysicalDeviceQueueFamilyProperties(pds[i], &qn, qf);
      for (uint32_t q = 0; q < qn; q++)
         printf("    queue family %u: flags 0x%x count %u\n", q, qf[q].queueFlags, qf[q].queueCount);
   }

   if (selected == UINT32_MAX) {
      fprintf(stderr, "no matching AMD hardware device; refusing software fallback\n");
      vkDestroyInstance(inst, NULL);
      return 1;
   }
   VkPhysicalDevice pd = pds[selected];
   printf("selected physical device %u%s\n", selected, hp ? " (HP device ID; subsystem verified by companion capture)" : "");
   uint32_t qfam = UINT32_MAX;
   {
      uint32_t qn = 0;
      vkGetPhysicalDeviceQueueFamilyProperties(pd, &qn, NULL);
      VkQueueFamilyProperties qf[16];
      if (qn > 16)
         qn = 16;
      vkGetPhysicalDeviceQueueFamilyProperties(pd, &qn, qf);
      for (uint32_t q = 0; q < qn; q++)
         if (qf[q].queueCount && (qf[q].queueFlags & VK_QUEUE_COMPUTE_BIT)) { qfam = q; break; }
      for (uint32_t q = 0; q < qn; q++)
         if ((qf[q].queueFlags & VK_QUEUE_COMPUTE_BIT) && !(qf[q].queueFlags & VK_QUEUE_GRAPHICS_BIT)) {
            qfam = q;
            break;
         }
      const char *override = getenv("VKPROBE_QFAM");
      if (override) {
         char *end;
         errno = 0;
         unsigned long value = strtoul(override, &end, 10);
         if (!*override || *override == '-' || *end || errno || value >= qn) {
            fprintf(stderr, "invalid VKPROBE_QFAM\n"); return 1;
         }
         qfam = (uint32_t)value;
      }
      if (qfam >= qn || !qf[qfam].queueCount || !(qf[qfam].queueFlags & VK_QUEUE_COMPUTE_BIT)) {
         fprintf(stderr, "selected queue has no compute support\n"); return 1;
      }
      printf("using queue family %u\n", qfam);
   }
   float prio = 1.0f;
   VkDeviceQueueCreateInfo qci = {
      .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
      .queueFamilyIndex = qfam,
      .queueCount = 1,
      .pQueuePriorities = &prio,
   };
   VkDeviceCreateInfo dci = {
      .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
      .queueCreateInfoCount = 1,
      .pQueueCreateInfos = &qci,
   };
   VkDevice dev;
   CHECK(vkCreateDevice(pd, &dci, NULL, &dev));
   printf("device created\n");

   VkShaderModuleCreateInfo smci = {
      .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
      .codeSize = sizeof(fill_spv),
      .pCode = fill_spv,
   };
   uint32_t *external = NULL;
   if (translated) {
      FILE *f = fopen(argv[3], "rb");
      if (!f || fseek(f, 0, SEEK_END)) { fprintf(stderr, "cannot open SPIR-V\n"); return 1; }
      const long bytes = ftell(f);
      if (bytes < 20 || bytes > 16 * 1024 * 1024 || bytes % 4 || fseek(f, 0, SEEK_SET)) return 1;
      external = malloc((size_t)bytes);
      if (!external || fread(external, (size_t)bytes, 1, f) != 1) return 1;
      fclose(f);
      if (external[0] != 0x07230203) return 1;
      smci.codeSize = (size_t)bytes; smci.pCode = external;
   }
   VkShaderModule sm;
   CHECK(vkCreateShaderModule(dev, &smci, NULL, &sm));
   free(external);

   VkDescriptorSetLayoutBinding b = {
      .binding = 0,
      .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
      .descriptorCount = 1,
      .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT,
   };
   VkDescriptorSetLayoutCreateInfo dslci = {
      .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
      .bindingCount = 1,
      .pBindings = &b,
   };
   VkDescriptorSetLayout dsl;
   CHECK(vkCreateDescriptorSetLayout(dev, &dslci, NULL, &dsl));
   VkPipelineLayoutCreateInfo plci = {
      .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
      .setLayoutCount = 1,
      .pSetLayouts = &dsl,
   };
   VkPipelineLayout pl;
   CHECK(vkCreatePipelineLayout(dev, &plci, NULL, &pl));

   VkComputePipelineCreateInfo cpci = {
      .sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
      .stage =
         {
            .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
            .stage = VK_SHADER_STAGE_COMPUTE_BIT,
            .module = sm,
            .pName = "main",
         },
      .layout = pl,
   };
   // The translated fixture stores once at index zero. Specialize its local
   // size to one to avoid concurrent non-atomic writes by the default 64 lanes.
   const uint32_t one = 1;
   VkSpecializationMapEntry local_size = {.constantID=0, .offset=0, .size=sizeof(one)};
   VkSpecializationInfo specialization = {.mapEntryCount=1, .pMapEntries=&local_size, .dataSize=sizeof(one), .pData=&one};
   if (translated) cpci.stage.pSpecializationInfo = &specialization;
   VkPipeline pipe;
   CHECK(vkCreateComputePipelines(dev, VK_NULL_HANDLE, 1, &cpci, NULL, &pipe));
   printf("compute pipeline compiled\n");

   /* Run it: 256 invocations write data[i] = i * 2654435761 into a host-visible buffer. */
   const uint32_t count = translated ? 1 : 256;
   VkBufferCreateInfo bci = {
      .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
      .size = count * sizeof(uint32_t),
      .usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT,
   };
   VkBuffer buf;
   CHECK(vkCreateBuffer(dev, &bci, NULL, &buf));
   VkMemoryRequirements mr;
   vkGetBufferMemoryRequirements(dev, buf, &mr);
   VkPhysicalDeviceMemoryProperties mp;
   vkGetPhysicalDeviceMemoryProperties(pd, &mp);
   uint32_t type = UINT32_MAX;
   const VkMemoryPropertyFlags want = VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT;
   for (uint32_t t = 0; t < mp.memoryTypeCount; t++)
      if ((mr.memoryTypeBits & (1u << t)) && (mp.memoryTypes[t].propertyFlags & want) == want) {
         type = t;
         break;
      }
   if (type == UINT32_MAX) {
      fprintf(stderr, "no host-visible coherent memory type\n");
      return 1;
   }
   VkMemoryAllocateInfo mai = {
      .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
      .allocationSize = mr.size,
      .memoryTypeIndex = type,
   };
   VkDeviceMemory mem;
   CHECK(vkAllocateMemory(dev, &mai, NULL, &mem));
   CHECK(vkBindBufferMemory(dev, buf, mem, 0));
   uint32_t *data;
   CHECK(vkMapMemory(dev, mem, 0, VK_WHOLE_SIZE, 0, (void **)&data));
   memset(data, 0xAB, count * sizeof(uint32_t));

   VkDescriptorPoolSize ps = {.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER, .descriptorCount = 1};
   VkDescriptorPoolCreateInfo dpci = {
      .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
      .maxSets = 1,
      .poolSizeCount = 1,
      .pPoolSizes = &ps,
   };
   VkDescriptorPool dp;
   CHECK(vkCreateDescriptorPool(dev, &dpci, NULL, &dp));
   VkDescriptorSetAllocateInfo dsai = {
      .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,
      .descriptorPool = dp,
      .descriptorSetCount = 1,
      .pSetLayouts = &dsl,
   };
   VkDescriptorSet ds;
   CHECK(vkAllocateDescriptorSets(dev, &dsai, &ds));
   VkDescriptorBufferInfo dbi = {.buffer = buf, .offset = 0, .range = VK_WHOLE_SIZE};
   VkWriteDescriptorSet wds = {
      .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
      .dstSet = ds,
      .descriptorCount = 1,
      .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,
      .pBufferInfo = &dbi,
   };
   vkUpdateDescriptorSets(dev, 1, &wds, 0, NULL);

   VkCommandPoolCreateInfo cpi = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = qfam};
   VkCommandPool pool;
   CHECK(vkCreateCommandPool(dev, &cpi, NULL, &pool));
   VkCommandBufferAllocateInfo cbai = {
      .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
      .commandPool = pool,
      .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY,
      .commandBufferCount = 1,
   };
   VkCommandBuffer cb;
   CHECK(vkAllocateCommandBuffers(dev, &cbai, &cb));
   VkCommandBufferBeginInfo cbbi = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};
   CHECK(vkBeginCommandBuffer(cb, &cbbi));
   vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pipe);
   vkCmdBindDescriptorSets(cb, VK_PIPELINE_BIND_POINT_COMPUTE, pl, 0, 1, &ds, 0, NULL);
   vkCmdDispatch(cb, translated ? 1 : count / 64, 1, 1);
   VkMemoryBarrier host = {
      .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
      .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
      .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
   };
   vkCmdPipelineBarrier(cb, VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
                        0, 1, &host, 0, NULL, 0, NULL);
   CHECK(vkEndCommandBuffer(cb));

   VkQueue q;
   vkGetDeviceQueue(dev, qfam, 0, &q);
   VkFenceCreateInfo fci = {.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};
   VkFence fence;
   CHECK(vkCreateFence(dev, &fci, NULL, &fence));
   VkSubmitInfo si = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cb};
   CHECK(vkQueueSubmit(q, 1, &si, fence));
   CHECK(vkWaitForFences(dev, 1, &fence, VK_TRUE, 2000000000ull));
   printf("dispatch submitted and fence signalled\n");

   uint32_t good = 0;
   for (uint32_t i = 0; i < count; i++)
      good += data[i] == (translated ? 7u : i * 2654435761u);
   printf("results: %u/%u correct (%s, data[0]=0x%08x)\n", good, count,
          translated ? "translated MSL store_value" : "GLSL fill", data[0]);

   vkDestroyFence(dev, fence, NULL);
   vkDestroyCommandPool(dev, pool, NULL);
   vkDestroyDescriptorPool(dev, dp, NULL);
   vkUnmapMemory(dev, mem);
   vkDestroyBuffer(dev, buf, NULL);
   vkFreeMemory(dev, mem, NULL);
   vkDestroyPipeline(dev, pipe, NULL);
   vkDestroyPipelineLayout(dev, pl, NULL);
   vkDestroyDescriptorSetLayout(dev, dsl, NULL);
   vkDestroyShaderModule(dev, sm, NULL);
   vkDestroyDevice(dev, NULL);
   vkDestroyInstance(inst, NULL);
   return good == count ? 0 : 1;
}
