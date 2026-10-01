shader_type spatial;
// Kart livery: glossy car paint with procedural patterns in part space, so
// liveries are a garage option and need no textures or UVs.
// Part space (Godot): +X right, +Y up, -Z forward (nose at z ~ -1.1).
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec4 primary : source_color = vec4(0.88, 0.2, 0.17, 1.0);
uniform vec4 secondary : source_color = vec4(1.0, 0.79, 0.24, 1.0);
uniform int pattern = 1;
uniform float roughness_v = 0.28;
uniform float clearcoat_v = 0.9;
uniform float flash = 0.0;      // hit / pickup flash
uniform vec4 flash_color : source_color = vec4(1.0);
uniform float ghost = 0.0;      // respawn blink

varying vec3 opos;

void vertex() {
	opos = VERTEX;
}

float band(float x, float c, float w) {
	float fw = fwidth(x) * 1.5;
	return smoothstep(w + fw, w - fw, abs(x - c));
}

vec3 hash3(vec3 p) {
	p = vec3(dot(p, vec3(127.1, 311.7, 74.7)), dot(p, vec3(269.5, 183.3, 246.1)), dot(p, vec3(113.5, 271.9, 124.6)));
	return fract(sin(p) * 43758.5453);
}

float voronoi(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	float d = 8.0;
	for (int z = -1; z <= 1; z++)
	for (int y = -1; y <= 1; y++)
	for (int x = -1; x <= 1; x++) {
		vec3 g = vec3(float(x), float(y), float(z));
		vec3 o = hash3(i + g);
		d = min(d, length(g + o - f));
	}
	return d;
}

void fragment() {
	vec3 p = opos;
	float m = 0.0;
	float edge = 0.0;
	if (pattern == 1) {
		m = band(p.x, 0.0, 0.075);
		edge = band(p.x, 0.0, 0.1) - m;
	} else if (pattern == 2) {
		m = max(band(p.x, 0.13, 0.035), band(p.x, -0.13, 0.035));
		m = max(m, band(p.y, 0.24, 0.02) * step(0.3, abs(p.x)));
	} else if (pattern == 3) {
		float t = -p.z;                                  // forward coordinate
		float tongue = 0.5 + 0.5 * sin(abs(p.x) * 26.0 + 1.1) * 0.8 + 0.25 * sin(abs(p.x) * 61.0);
		float boundary = 0.25 + tongue * 0.35;
		float fw = fwidth(t) * 1.5;
		m = smoothstep(boundary - fw, boundary + fw, t);
		edge = smoothstep(boundary + 0.12 - fw, boundary + 0.12 + fw, t);
	} else if (pattern == 4) {
		vec3 q = floor(p * 7.0);
		float c = mod(q.x + q.y + q.z, 2.0);
		m = c;
	} else if (pattern == 5) {
		float d = voronoi(p * 11.0);
		m = smoothstep(0.34, 0.30, d) - smoothstep(0.2, 0.16, d) * 0.7;
	}
	vec3 col = mix(primary.rgb, secondary.rgb, clamp(m, 0.0, 1.0));
	if (pattern == 1) col = mix(col, vec3(1.0), clamp(edge, 0.0, 1.0));
	if (pattern == 3) col = mix(col, mix(secondary.rgb, vec3(1.0, 0.95, 0.6), 0.6), clamp(edge, 0.0, 1.0));
	ALBEDO = mix(col, flash_color.rgb, flash);
	EMISSION = flash_color.rgb * flash * 0.6;
	ROUGHNESS = roughness_v;
	METALLIC = 0.05;
	CLEARCOAT = clearcoat_v;
	CLEARCOAT_ROUGHNESS = 0.06;
	RIM = 0.3;
	RIM_TINT = 0.6;
	if (ghost > 0.0) {
		ALPHA = 1.0;
		// dither-fade blink (keeps opaque pipeline)
		float n = fract(sin(dot(FRAGCOORD.xy, vec2(12.9898, 78.233))) * 43758.5453);
		if (n < ghost) discard;
	}
}
