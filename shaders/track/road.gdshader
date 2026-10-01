shader_type spatial;
// Road strip. UV.x spans the full strip (curb | road | curb), UV.y = metres/4.
// COLOR.r = curb visibility (1 in corners), COLOR.g = road width / 20.
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 asphalt : source_color = vec4(0.36, 0.35, 0.38, 1.0);
uniform vec4 asphalt_dark : source_color = vec4(0.24, 0.235, 0.26, 1.0);
uniform vec4 line_color : source_color = vec4(0.96, 0.95, 0.9, 1.0);
uniform vec4 curb_a : source_color = vec4(0.9, 0.12, 0.1, 1.0);
uniform vec4 curb_b : source_color = vec4(0.97, 0.97, 0.95, 1.0);
uniform float curb_w = 1.3;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	float w = COLOR.g * 20.0;
	float lat = UV.x * (w + 2.0 * curb_w) - (w * 0.5 + curb_w);
	float along = UV.y * 4.0;
	float alat = abs(lat);
	vec2 np = wpos.xz;
	float n1 = texture(noise_tex, np * 0.05).r;
	float n2 = texture(noise_tex, np * 0.43).r;
	float n3 = texture(noise_tex, np * 2.3).r;
	vec3 col = mix(asphalt_dark.rgb, asphalt.rgb, smoothstep(0.25, 0.75, n1));
	col *= 0.9 + 0.2 * n2;
	col *= 0.93 + 0.14 * n3;
	// darker racing groove in the middle third
	col *= 1.0 - 0.07 * smoothstep(w * 0.35, 0.0, alat);
	float rough = 0.78 - 0.1 * n2;
	// edge lines
	float fw = fwidth(alat) * 1.5;
	float line = smoothstep(w * 0.5 - 0.5 - fw, w * 0.5 - 0.5 + fw, alat) * (1.0 - smoothstep(w * 0.5 - 0.2 - fw, w * 0.5 - 0.2 + fw, alat));
	col = mix(col, line_color.rgb * (0.9 + 0.1 * n3), line * (0.85 + 0.15 * n2));
	// curbs
	if (alat > w * 0.5) {
		float curb = COLOR.r;
		float stripe = step(0.5, fract(along / 3.0));
		vec3 cc = mix(curb_a.rgb, curb_b.rgb, stripe) * (0.92 + 0.12 * n3);
		vec3 shoulder = mix(vec3(0.55, 0.52, 0.5), vec3(0.62, 0.6, 0.57), n2);
		col = mix(shoulder, cc, smoothstep(0.35, 0.65, curb));
		rough = mix(0.8, 0.45, curb);
	}
	ALBEDO = col;
	ROUGHNESS = rough;
	SPECULAR = 0.4;
}
