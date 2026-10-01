shader_type spatial;
// Flapping critters (gulls, butterflies). Wing vertices (|x| > 0.05) swing
// up/down with a per-instance phase in INSTANCE_CUSTOM.a.
render_mode cull_disabled, diffuse_burley;
uniform float flap = 0.5;
uniform float rate = 9.0;
uniform bool use_instance_color = false;
varying vec4 tint;

void vertex() {
	float ph = INSTANCE_CUSTOM.a * 6.283;
	float w = smoothstep(0.05, 1.0, abs(VERTEX.x));
	float s = sin(TIME * rate + ph);
	VERTEX.y += s * flap * w * (0.6 + abs(VERTEX.x) * 0.6);
	VERTEX.x *= 1.0 - abs(s) * 0.15 * w;
	tint = use_instance_color ? COLOR : vec4(1.0);
}

void fragment() {
	vec3 c = use_instance_color ? tint.rgb : COLOR.rgb;
	ALBEDO = c;
	ROUGHNESS = 0.7;
	RIM = 0.4;
	BACKLIGHT = c * 0.4;
}
