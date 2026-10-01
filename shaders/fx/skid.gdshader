shader_type spatial;
// Tyre marks: soft edges, broken-up by noise, fade out by age (UV.x = birth).
render_mode blend_mix, depth_draw_never, cull_disabled, diffuse_burley, specular_disabled;
uniform float now = 0.0;
uniform float life = 14.0;
varying vec3 wpos;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

void vertex() {
	wpos = VERTEX;
	NORMAL = vec3(0.0, 1.0, 0.0);
}

void fragment() {
	float age = now - UV.x;
	float fade = 1.0 - smoothstep(life * 0.6, life, age);
	float edge = smoothstep(0.0, 0.3, UV.y) * smoothstep(1.0, 0.7, UV.y);
	float n = vnoise(wpos.xz * 3.0) * 0.6 + vnoise(wpos.xz * 11.0) * 0.4;
	ALBEDO = COLOR.rgb * (0.8 + 0.4 * n);
	ROUGHNESS = 0.9;
	ALPHA = COLOR.a * fade * edge * (0.55 + 0.45 * n);
}
