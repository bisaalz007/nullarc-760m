#include <metal_stdlib>
using namespace metal;
kernel void store_value(device uint *out [[buffer(0)]]) { out[0] = 7; }
struct VertexOut { float4 position [[position]]; };
vertex VertexOut triangle_vertex(uint id [[vertex_id]]) {
    VertexOut out;
    out.position = float4(id == 1 ? 3.0f : -1.0f, id == 2 ? 3.0f : -1.0f, 0.0f, 1.0f);
    return out;
}
fragment float4 solid_fragment() { return float4(0.25f, 0.5f, 0.75f, 1.0f); }
