shader_type spatial;
// Hot-air balloon envelope: bold vertical gores alternating two colours.
uniform vec4 color_a : source_color = vec4(0.94, 0.23, 0.21, 1.0);
uniform vec4 color_b : source_color = vec4(1.0, 0.82, 0.25, 1.0);
void fragment() {
	float g = step(0.5, fract(UV.x * 12.0));
	vec3 c = mix(color_a.rgb, color_b.rgb, g);
	c = mix(c, vec3(1.0), smoothstep(0.9, 0.95, UV.y) * 0.0);
	ALBEDO = c;
	ROUGHNESS = 0.55;
	RIM = 0.3;
	BACKLIGHT = c * 0.3;
}
