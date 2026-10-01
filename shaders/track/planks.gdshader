shader_type spatial;
// Wooden bridge deck: textured boards across the road, per-board tone and
// offset, dark gaps, nails, sun-bleached edges.
render_mode diffuse_burley;
uniform sampler2D wood_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wood_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float board = 0.5;
varying vec3 wnrm;

float h(float n) { return fract(sin(n * 91.3458) * 47453.5453); }

void vertex() {
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float along = UV.y * 4.0;
	float k = floor(along / board);
	float f = fract(along / board);
	float t = h(k);
	vec2 tuv = vec2(UV.x * 4.0 + t * 7.0, f * 0.12 + t);
	vec3 col = texture(wood_alb, tuv).rgb * mix(0.75, 1.15, t);
	col = mix(col, col * vec3(1.1, 1.05, 0.95) + 0.05, smoothstep(0.3, 0.0, abs(UV.x - 0.5) - 0.2) * 0.0 + h(k + 3.0) * 0.15);
	float gap = smoothstep(0.0, 0.06, f) * smoothstep(1.0, 0.94, f);
	col *= mix(0.2, 1.0, gap);
	float nx = fract(UV.x * 6.0);
	float nail = smoothstep(0.03, 0.0, length(vec2(nx - 0.5, (f - 0.5) * 0.7)) - 0.02);
	col = mix(col, vec3(0.32, 0.32, 0.34), nail);
	vec2 pn = texture(wood_nrm, tuv).rg * 2.0 - 1.0;
	NORMAL = normalize((VIEW_MATRIX * vec4(normalize(wnrm + vec3(pn.x, 0.0, pn.y) * 0.5), 0.0)).xyz);
	ALBEDO = col;
	ROUGHNESS = 0.78;
	AO = gap * 0.6 + 0.4;
}
