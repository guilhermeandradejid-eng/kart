shader_type canvas_item;
// Iris wipe with a scalloped (star-ish) edge — the transition between scenes.
uniform float progress : hint_range(0.0, 1.0) = 0.0;
uniform vec4 tint : source_color = vec4(0.05, 0.03, 0.09, 1.0);
uniform vec4 rim : source_color = vec4(1.0, 0.62, 0.12, 1.0);

void fragment() {
	vec2 res = 1.0 / SCREEN_PIXEL_SIZE;
	vec2 p = (UV - 0.5) * vec2(res.x / res.y, 1.0);
	float a = atan(p.y, p.x);
	float r = length(p) * (1.0 + 0.045 * sin(a * 9.0 + progress * 6.0));
	float radius = (1.0 - progress) * 1.25;
	float inside = smoothstep(radius - 0.004, radius + 0.004, r);
	float edge = smoothstep(radius - 0.03, radius, r) * (1.0 - smoothstep(radius, radius + 0.004, r));
	vec3 col = mix(tint.rgb, rim.rgb, edge);
	COLOR = vec4(col, max(inside, edge) * step(0.001, progress));
}
