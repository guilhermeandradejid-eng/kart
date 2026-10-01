shader_type spatial;
// Wooden bridge deck: boards across the road, per-board tone, dark gaps, grain.
render_mode diffuse_burley;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 wood_a : source_color = vec4(0.62, 0.42, 0.24, 1.0);
uniform vec4 wood_b : source_color = vec4(0.48, 0.3, 0.16, 1.0);
uniform float board = 0.45;

float h(float n) { return fract(sin(n * 91.3458) * 47453.5453); }

void fragment() {
	float along = UV.y * 4.0;
	float k = floor(along / board);
	float f = fract(along / board);
	float t = h(k);
	vec3 col = mix(wood_b.rgb, wood_a.rgb, t);
	float grain = texture(noise_tex, vec2(UV.x * 3.0 + t * 7.0, f * 0.2 + k * 0.37)).r;
	col *= 0.8 + 0.35 * grain;
	float gap = smoothstep(0.0, 0.05, f) * smoothstep(1.0, 0.95, f);
	col *= mix(0.25, 1.0, gap);
	// nails
	float nx = fract(UV.x * 6.0);
	float nail = smoothstep(0.03, 0.0, length(vec2(nx - 0.5, (f - 0.5) * 0.7)) - 0.02);
	col = mix(col, vec3(0.3, 0.3, 0.32), nail);
	ALBEDO = col;
	ROUGHNESS = 0.75;
}
