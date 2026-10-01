shader_type spatial;
// Item box shell: glassy, iridescent rainbow sweep, bright fresnel rim.
render_mode blend_mix, cull_back, depth_draw_opaque, diffuse_burley, specular_schlick_ggx;
uniform float alpha_v = 0.5;
uniform float pop = 0.0;   // flashes white when collected / respawning

vec3 hue(float h) {
	return clamp(abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
}

void fragment() {
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 2.0);
	vec3 wn = (INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz;
	vec3 rainbow = hue(TIME * 0.35 + wn.y * 0.3 + wn.x * 0.2 + fres * 0.5);
	vec3 col = mix(vec3(0.85, 0.95, 1.0), rainbow, 0.65);
	ALBEDO = col;
	EMISSION = rainbow * (0.35 + fres * 1.6) + vec3(pop * 2.0);
	ROUGHNESS = 0.05;
	SPECULAR = 0.8;
	ALPHA = clamp(alpha_v + fres * 0.45 + pop, 0.0, 1.0);
}
