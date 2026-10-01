shader_type spatial;
// Stylised tropical water: depth-tinted turquoise -> deep blue, animated normal
// maps, refraction of the sea floor, shore foam bands and sun glints.
render_mode blend_mix, depth_draw_always, cull_disabled, diffuse_burley, specular_schlick_ggx;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, repeat_disable, filter_nearest;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_linear_mipmap, repeat_enable;
uniform vec4 shallow : source_color = vec4(0.22, 0.95, 0.86, 1.0);
uniform vec4 deep : source_color = vec4(0.02, 0.36, 0.7, 1.0);
uniform vec4 foam_color : source_color = vec4(1.0);
uniform float clarity = 0.28;
uniform float wave_height = 0.12;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float w = sin(wpos.x * 0.08 + TIME * 0.9) * 0.6 + sin(wpos.z * 0.11 - TIME * 1.1) * 0.4;
	VERTEX.y += w * wave_height;
}

void fragment() {
	vec2 uv1 = wpos.xz * 0.045 + vec2(TIME * 0.012, TIME * 0.008);
	vec2 uv2 = wpos.xz * 0.11 - vec2(TIME * 0.018, -TIME * 0.011);
	vec3 n1 = texture(normal_tex, uv1).rgb;
	vec3 n2 = texture(normal_tex, uv2).rgb;
	NORMAL_MAP = normalize(mix(n1, n2, 0.5));
	NORMAL_MAP_DEPTH = 0.6;

	float d = texture(depth_tex, SCREEN_UV).r;
	vec4 ndc = vec4(SCREEN_UV * 2.0 - 1.0, d, 1.0);
	vec4 view = INV_PROJECTION_MATRIX * ndc;
	view.xyz /= view.w;
	float scene_depth = -view.z;
	float surf_depth = -VERTEX.z;
	float depth = max(scene_depth - surf_depth, 0.0);

	vec2 refr_uv = SCREEN_UV + (NORMAL_MAP.xy - 0.5) * 0.03 * clamp(depth, 0.0, 1.0);
	vec3 below = texture(screen_tex, refr_uv).rgb;
	float t = exp(-depth * clarity);
	vec3 water = mix(deep.rgb, shallow.rgb, clamp(t * 1.4, 0.0, 1.0));
	vec3 col = mix(water, below * shallow.rgb * 1.2, t * 0.75);

	// shore foam: solid lip + travelling bands
	float nf = texture(noise_tex, wpos.xz * 0.2 + TIME * 0.03).r;
	float lip = 1.0 - smoothstep(0.05, 0.35 + nf * 0.3, depth);
	float bands = smoothstep(0.75, 0.95, sin(depth * 5.0 - TIME * 1.6 + nf * 3.0) * 0.5 + 0.5) * (1.0 - smoothstep(0.3, 2.2, depth));
	float foam = clamp(lip + bands * 0.7, 0.0, 1.0) * smoothstep(0.35, 0.55, nf + 0.3);
	col = mix(col, foam_color.rgb, foam);

	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 4.0);
	ALBEDO = col;
	ROUGHNESS = mix(0.04, 0.6, foam);
	SPECULAR = 0.6;
	METALLIC = 0.0;
	// sun glitter: sparse twinkles where two drifting noise layers peak together
	float g1 = texture(noise_tex, wpos.xz * 0.7 + vec2(TIME * 0.05, 0.0)).r;
	float g2 = texture(noise_tex, wpos.xz * 1.1 - vec2(0.0, TIME * 0.06)).r;
	float glitter = smoothstep(0.78, 0.86, g1 * g2 * 1.9) * (1.0 - foam) * (1.0 - t);
	EMISSION = col * 0.08 + vec3(0.6, 0.85, 1.0) * fres * 0.15 + vec3(1.0, 0.95, 0.82) * glitter * 3.0;
	ALPHA = 1.0;
}
