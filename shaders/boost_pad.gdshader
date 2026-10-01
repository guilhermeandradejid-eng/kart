shader_type spatial;
// Boost pad: chevrons scrolling toward +UV.y (the direction of travel), hot
// gradient, pulsing glow. UV.x across, UV.y along.
render_mode diffuse_burley, specular_schlick_ggx;
uniform vec4 hot : source_color = vec4(1.0, 0.85, 0.2, 1.0);
uniform vec4 warm : source_color = vec4(1.0, 0.35, 0.05, 1.0);
uniform vec4 base : source_color = vec4(0.25, 0.08, 0.02, 1.0);
uniform float speed = 1.6;
uniform float glow = 3.0;
uniform float flip = 0.0;

void fragment() {
	vec2 uv = UV;
	if (flip > 0.5) uv.y = 1.0 - uv.y;
	float x = abs(uv.x - 0.5) * 2.0;
	float v = uv.y * 3.0 - x * 0.55 - TIME * speed;
	float chev = smoothstep(0.42, 0.5, fract(v)) * (1.0 - smoothstep(0.78, 0.86, fract(v)));
	float border = smoothstep(0.86, 0.9, x);
	vec3 grad = mix(warm.rgb, hot.rgb, fract(v));
	vec3 col = mix(base.rgb, grad, chev);
	col = mix(col, hot.rgb, border);
	float pulse = 0.75 + 0.25 * sin(TIME * 8.0);
	ALBEDO = col;
	EMISSION = (grad * chev + hot.rgb * border) * glow * pulse;
	ROUGHNESS = 0.3;
}
