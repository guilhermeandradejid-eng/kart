shader_type spatial;
// Terrain: vertex-painted biomes (COLOR.rgb) + procedural detail. COLOR.a is
// the sand weight: grass gets clumpy hue variation, sand gets wind ripples and
// sparkle; both fade detail with distance to avoid shimmer.
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 grass_tip : source_color = vec4(0.62, 0.86, 0.32, 1.0);

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec3 base = COLOR.rgb;
	float sand = COLOR.a;
	float dist = length(wpos - CAMERA_POSITION_WORLD);
	float fade = 1.0 - smoothstep(60.0, 240.0, dist);
	float n1 = texture(noise_tex, wpos.xz * 0.021).r;
	float n2 = texture(noise_tex, wpos.xz * 0.13).r;
	float n3 = texture(noise_tex, wpos.xz * 0.9).r;
	float n4 = texture(noise_tex, wpos.xz * 3.7).r;
	// grass: clumps + sun-bleached tips
	vec3 g = base * (0.82 + 0.3 * n1);
	g = mix(g, grass_tip.rgb * (0.8 + 0.2 * n2), smoothstep(0.55, 0.8, n2) * 0.35);
	g *= mix(1.0, 0.85 + 0.3 * n4, fade);
	// sand: ripples perpendicular to the sea breeze + sparkle
	float ripple = sin(wpos.x * 2.1 + wpos.z * 0.7 + n2 * 6.0) * 0.5 + 0.5;
	vec3 s = base * (0.94 + 0.08 * n1) * mix(1.0, 0.94 + 0.08 * ripple, fade);
	s *= mix(1.0, 0.95 + 0.1 * n4, fade);
	vec3 col = mix(g, s, smoothstep(0.35, 0.65, sand));
	ALBEDO = col;
	float sparkle = step(0.985, n4) * sand * fade;
	ROUGHNESS = mix(0.92, 0.85, sand) - sparkle * 0.6;
	SPECULAR = 0.25 + sparkle * 0.8;
}
