shader_type sky;
// Sunny tropical sky: vertical gradient, soft sun + halo, stylised drifting
// cumulus built from layered noise projected on a dome.
uniform vec4 zenith : source_color = vec4(0.16, 0.45, 0.9, 1.0);
uniform vec4 horizon : source_color = vec4(0.62, 0.86, 1.0, 1.0);
uniform vec4 ground : source_color = vec4(0.32, 0.55, 0.62, 1.0);
uniform vec4 sun_color : source_color = vec4(1.0, 0.93, 0.78, 1.0);
uniform vec4 cloud_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform vec4 cloud_shadow : source_color = vec4(0.68, 0.78, 0.92, 1.0);
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float cloud_cover = 0.52;
uniform float time_scale = 0.004;

void sky() {
	vec3 d = EYEDIR;
	float h = d.y;
	vec3 col = mix(horizon.rgb, zenith.rgb, pow(clamp(h, 0.0, 1.0), 0.6));
	col = mix(col, ground.rgb, smoothstep(0.0, -0.08, h));
	vec3 sd = LIGHT0_DIRECTION;
	float sdot = max(dot(d, sd), 0.0);
	col += sun_color.rgb * (pow(sdot, 900.0) * 18.0 + pow(sdot, 12.0) * 0.35 + pow(sdot, 3.0) * 0.08);
	if (h > 0.0) {
		vec2 p = d.xz / (h + 0.18);
		float t = TIME * time_scale;
		float n = texture(noise_tex, p * 0.18 + vec2(t, t * 0.4)).r * 0.6
			+ texture(noise_tex, p * 0.45 - vec2(t * 1.7, 0.0)).r * 0.3
			+ texture(noise_tex, p * 1.3 + vec2(0.0, t * 2.0)).r * 0.1;
		float c = smoothstep(1.0 - cloud_cover, 1.0 - cloud_cover + 0.2, n);
		float shade = smoothstep(0.35, 0.9, texture(noise_tex, p * 0.18 + vec2(t, t * 0.4) + sd.xz * 0.02).r);
		vec3 cc = mix(cloud_shadow.rgb, cloud_color.rgb, 1.0 - shade * 0.6);
		cc += sun_color.rgb * pow(sdot, 6.0) * 0.4;
		c *= smoothstep(0.0, 0.12, h);
		col = mix(col, cc, c * 0.95);
	}
	COLOR = col;
}
