shader_type spatial;
render_mode diffuse_burley;
void fragment() {
	vec2 q = floor(UV * vec2(1.0, 2.0));
	float c = mod(q.x + q.y, 2.0);
	vec2 fw = fwidth(UV * vec2(1.0, 2.0));
	ALBEDO = mix(vec3(0.05), vec3(0.95), c);
	ROUGHNESS = 0.6;
}
