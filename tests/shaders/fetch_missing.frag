#version 450
layout(input_attachment_index=0,set=3,binding=192) uniform subpassInput color;
layout(input_attachment_index=2,set=3,binding=194) uniform subpassInput missing;
layout(location=0) out vec4 out_color;
void main() { out_color=subpassLoad(color)+subpassLoad(missing); }
