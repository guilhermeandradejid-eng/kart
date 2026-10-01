shader_type spatial;
// Splat-mapped terrain. COLOR = weights (R grass, G sand, B dirt, A rock).
// Height-based blending (each texture's height in mask.g) gives crisp,
// natural transitions; two rotated scales break tiling; rock is triplanar on
// slopes; sand darkens and gets glossy near the waterline; UV.x = cavity AO.
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D grass_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D grass_msk : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D sand_msk : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D dirt_msk : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D rock_msk : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float scale = 0.16;          // texture repeats per metre
uniform float rock_scale = 0.09;
uniform float normal_strength = 0.9;
uniform vec4 grass_tint_a : source_color = vec4(1.0, 1.0, 0.86, 1.0);
uniform vec4 grass_tint_b : source_color = vec4(0.82, 1.0, 0.9, 1.0);
uniform float water_level = 0.0;
uniform int debug_view = 0;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec2 rot(vec2 p, float a) {
	float c = cos(a), s = sin(a);
	return vec2(c * p.x - s * p.y, s * p.x + c * p.y);
}

void sample_top(sampler2D alb, sampler2D nrm, sampler2D msk, vec2 uv, float macro, out vec3 a, out float h, out vec2 n, out float r) {
	vec2 uv2 = rot(uv, 1.3) * 0.37 + 0.21;
	float m = smoothstep(0.35, 0.65, macro) * 0.6;
	a = mix(texture(alb, uv).rgb, texture(alb, uv2).rgb, m);
	vec3 m1 = mix(texture(msk, uv).rgb, texture(msk, uv2).rgb, m);
	h = m1.g;
	r = m1.r;
	n = mix(texture(nrm, uv).rg, texture(nrm, uv2).rg, m) * 2.0 - 1.0;
}

void fragment() {
	vec4 w = clamp(COLOR, vec4(0.0), vec4(1.0));
	vec2 uv = wpos.xz * scale;
	float dist = length(wpos - CAMERA_POSITION_WORLD);
	float macro = texture(noise_tex, uv * 0.031).r;

	vec3 ga; float gh; vec2 gn; float gr;
	vec3 sa; float sh; vec2 sn; float sr;
	vec3 da; float dh; vec2 dn; float dr;
	sample_top(grass_alb, grass_nrm, grass_msk, uv, macro, ga, gh, gn, gr);
	sample_top(sand_alb, sand_nrm, sand_msk, uv * 0.8, macro, sa, sh, sn, sr);
	sample_top(dirt_alb, dirt_nrm, dirt_msk, uv * 1.1, macro, da, dh, dn, dr);

	// triplanar rock
	vec3 bw = pow(abs(wnrm), vec3(4.0));
	bw /= (bw.x + bw.y + bw.z + 1e-5);
	vec3 ra = texture(rock_alb, wpos.zy * rock_scale).rgb * bw.x + texture(rock_alb, wpos.xz * rock_scale).rgb * bw.y
		+ texture(rock_alb, wpos.xy * rock_scale).rgb * bw.z;
	float rh = texture(rock_msk, wpos.zy * rock_scale).g * bw.x + texture(rock_msk, wpos.xz * rock_scale).g * bw.y
		+ texture(rock_msk, wpos.xy * rock_scale).g * bw.z;
	vec2 rn = texture(rock_nrm, wpos.xz * rock_scale).rg * 2.0 - 1.0;

	// grass macro tint (sun-bleached / lush patches)
	float tint = texture(noise_tex, wpos.xz * 0.006).r;
	ga *= mix(grass_tint_b.rgb, grass_tint_a.rgb, smoothstep(0.3, 0.7, tint));

	// height blend
	vec4 hw = w * (vec4(gh, sh, dh, rh) * 0.6 + 0.4);
	hw = pow(max(hw, vec4(0.0)) + 1e-4, vec4(6.0));
	hw /= (hw.r + hw.g + hw.b + hw.a + 1e-5);

	vec3 albedo = ga * hw.r + sa * hw.g + da * hw.b + ra * hw.a;
	float rough = gr * hw.r + sr * hw.g + dr * hw.b + 0.85 * hw.a;
	vec2 pn = gn * hw.r + sn * hw.g + dn * hw.b + rn * hw.a;

	// wet sand / shoreline
	float wet = (1.0 - smoothstep(water_level + 0.05, water_level + 0.9, wpos.y)) * (hw.g + hw.b * 0.5);
	albedo = mix(albedo, albedo * vec3(0.62, 0.6, 0.58), wet);
	rough = mix(rough, 0.25, wet);

	float fade = 1.0 - smoothstep(80.0, 260.0, dist);
	pn *= normal_strength * fade;
	vec3 n_world = normalize(wnrm + vec3(pn.x, 0.0, pn.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);
	ALBEDO = albedo;
	ROUGHNESS = rough;
	SPECULAR = 0.35 + wet * 0.3;
	AO = UV.x;
	AO_LIGHT_AFFECT = 0.4;
	if (debug_view > 0) {
		vec3 d = vec3(0.0);
		if (debug_view == 1) d = albedo;
		if (debug_view == 2) d = n_world * 0.5 + 0.5;
		if (debug_view == 3) d = hw.rgb + vec3(hw.a);
		if (debug_view == 4) d = vec3(UV.x, rough, w.a);
		bool bad = any(isnan(d)) || any(isinf(d));
		ALBEDO = vec3(0.0);
		ROUGHNESS = 1.0;
		SPECULAR = 0.0;
		AO = 1.0;
		NORMAL = VIEW_MATRIX[1].xyz;
		EMISSION = bad ? vec3(4.0, 0.0, 4.0) : d;
	}
}
