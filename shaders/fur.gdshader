shader_type spatial;
// Character fur / cloth: vertex-coloured albedo, soft fuzz sheen at grazing
// angles, warm translucency (ears glow when backlit), and an HSV remap so the
// same Guará mesh can wear different colourways for rival drivers.
render_mode diffuse_burley, specular_schlick_ggx;

uniform float hue = 0.0;         // hue offset (turns)
uniform float sat = 1.0;
uniform float val = 1.0;
uniform float remap_min_sat = 0.25;  // only remap saturated colours (keep black/white)
uniform float roughness_v = 0.82;
uniform float sheen = 0.35;
uniform vec4 sheen_color : source_color = vec4(1.0, 0.86, 0.7, 1.0);
uniform float translucency = 0.25;
uniform float flash = 0.0;
uniform vec4 flash_color : source_color = vec4(1.0);

vec3 rgb2hsv(vec3 c) {
	vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
	vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
	vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
	float d = q.x - min(q.w, q.y);
	float e = 1.0e-10;
	return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
	vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
	return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

void fragment() {
	vec3 c = COLOR.rgb;
	if (hue != 0.0 || sat != 1.0 || val != 1.0) {
		vec3 h = rgb2hsv(c);
		float w = smoothstep(remap_min_sat, remap_min_sat + 0.15, h.y);
		vec3 h2 = vec3(fract(h.x + hue), clamp(h.y * sat, 0.0, 1.0), clamp(h.z * val, 0.0, 1.0));
		c = mix(c, hsv2rgb(h2), w);
	}
	float ndv = clamp(dot(NORMAL, VIEW), 0.0, 1.0);
	float fres = pow(1.0 - ndv, 2.5);
	ALBEDO = mix(c, flash_color.rgb, flash);
	ROUGHNESS = roughness_v;
	SPECULAR = 0.3;
	EMISSION = (sheen_color.rgb * c * fres * sheen) + flash_color.rgb * flash * 0.5;
	BACKLIGHT = c * translucency;
}
