shader_type spatial;
// Road strip. UV.x spans the full strip (curb | road | curb), UV.y = metres/4.
// COLOR.r = curb visibility (1 in corners), COLOR.g = road width / 20.
// Textured asphalt (anti-tiled), tyre grime on the racing line, dust drifting
// in from the shoulders, worn painted edge lines and red/white curbs.
render_mode diffuse_burley, specular_schlick_ggx;

uniform sampler2D asphalt_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D asphalt_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D asphalt_msk : filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D noise_tex : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform vec4 line_color : source_color = vec4(0.97, 0.96, 0.9, 1.0);
uniform vec4 curb_a : source_color = vec4(0.92, 0.14, 0.11, 1.0);
uniform vec4 curb_b : source_color = vec4(0.98, 0.97, 0.95, 1.0);
uniform vec4 dust_color : source_color = vec4(0.78, 0.66, 0.48, 1.0);
uniform float curb_w = 1.3;
uniform float tex_scale = 0.2;

varying vec3 wpos;
varying vec3 wnrm;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float w = COLOR.g * 20.0;
	float lat = UV.x * (w + 2.0 * curb_w) - (w * 0.5 + curb_w);
	float along = UV.y * 4.0;
	float alat = abs(lat);
	vec2 uv = wpos.xz * tex_scale;
	vec2 uv2 = vec2(uv.y, -uv.x) * 0.41 + 0.37;
	float macro = texture(noise_tex, wpos.xz * 0.012).r;
	float mb = smoothstep(0.4, 0.6, macro) * 0.5;
	vec3 col = mix(texture(asphalt_alb, uv).rgb, texture(asphalt_alb, uv2).rgb, mb);
	vec3 msk = mix(texture(asphalt_msk, uv).rgb, texture(asphalt_msk, uv2).rgb, mb);
	vec2 pn = mix(texture(asphalt_nrm, uv).rg, texture(asphalt_nrm, uv2).rg, mb) * 2.0 - 1.0;
	float rough = msk.r;
	float n2 = texture(noise_tex, wpos.xz * 0.11).r;
	// tyre grime: two darker wheel bands either side of the centre + racing line
	float grime = smoothstep(w * 0.42, w * 0.12, alat) * (0.55 + 0.45 * n2);
	col *= 1.0 - 0.16 * grime;
	rough -= 0.08 * grime;
	// dust blown in from the shoulders
	float dust = smoothstep(w * 0.28, w * 0.5, alat) * smoothstep(0.35, 0.7, n2 + texture(noise_tex, wpos.xz * 0.37).r * 0.4);
	col = mix(col, dust_color.rgb * (0.85 + 0.3 * msk.g), dust * 0.55);
	// worn edge lines
	float fw = fwidth(alat) * 1.5;
	float line = smoothstep(w * 0.5 - 0.55 - fw, w * 0.5 - 0.55 + fw, alat) * (1.0 - smoothstep(w * 0.5 - 0.25 - fw, w * 0.5 - 0.25 + fw, alat));
	float wear = smoothstep(0.25, 0.6, texture(noise_tex, wpos.xz * 0.8).r + msk.g * 0.4);
	col = mix(col, line_color.rgb * (0.85 + 0.15 * msk.g), line * wear);
	// curbs
	if (alat > w * 0.5) {
		float curb = COLOR.r;
		float stripe = step(0.5, fract(along / 3.0));
		vec3 cc = mix(curb_a.rgb, curb_b.rgb, stripe) * (0.86 + 0.2 * msk.g);
		cc = mix(cc, cc * 0.6, (1.0 - wear) * 0.35);
		vec3 shoulder = mix(dust_color.rgb * 0.9, vec3(0.62, 0.6, 0.57), n2);
		col = mix(shoulder, cc, smoothstep(0.35, 0.65, curb));
		rough = mix(0.85, 0.42, curb);
		pn *= 0.3;
	}
	vec3 n_world = normalize(wnrm + vec3(pn.x, 0.0, pn.y) * 0.6);
	NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);
	ALBEDO = col;
	ROUGHNESS = clamp(rough, 0.2, 1.0);
	SPECULAR = 0.45;
}
