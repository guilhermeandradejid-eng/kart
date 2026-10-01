shader_type spatial;
render_mode blend_mix, cull_disabled, depth_draw_opaque, diffuse_burley;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 water : source_color = vec4(0.72, 0.95, 1.0, 1.0);
uniform vec4 deep : source_color = vec4(0.2, 0.62, 0.85, 1.0);

void fragment() {
	vec2 uv = UV;
	float s1 = texture(noise_tex, vec2(uv.x * 3.0, uv.y * 0.6 - TIME * 1.4)).r;
	float s2 = texture(noise_tex, vec2(uv.x * 7.0 + 0.3, uv.y * 1.3 - TIME * 2.3)).r;
	float streak = smoothstep(0.45, 0.8, s1 * 0.6 + s2 * 0.4);
	vec3 col = mix(deep.rgb, water.rgb, streak);
	col = mix(col, vec3(1.0), smoothstep(2.4, 3.0, uv.y) * 0.8 + streak * 0.2);
	float edge = smoothstep(0.0, 0.08, uv.x) * smoothstep(1.0, 0.92, uv.x);
	ALBEDO = col;
	EMISSION = col * 0.25;
	ROUGHNESS = 0.2;
	ALPHA = clamp((0.55 + streak * 0.45) * edge, 0.0, 1.0);
}
