shader_type spatial;
// Generic stylised surface for vertex-coloured props (rock, wood, straw, plastic,
// fabric, paint...). Vertex colour x tint, soft rim, optional value noise to
// break up flat colour, optional wind sway driven by vertex-colour alpha.
render_mode diffuse_burley, specular_schlick_ggx;

uniform vec4 tint : source_color = vec4(1.0);
uniform float roughness_v = 0.75;
uniform float metallic_v = 0.0;
uniform float rim_v = 0.2;
uniform float detail = 0.08;        // albedo noise amount
uniform float detail_scale = 1.5;
uniform float wind = 0.0;           // metres of sway at alpha = 1
uniform float wind_speed = 1.3;
uniform bool use_vertex_color = true;
uniform float emission_v = 0.0;
uniform float instance_tint = 0.0;  // use INSTANCE_CUSTOM.rgb as tint (crowds)
uniform float bounce = 0.0;
uniform float bob = 0.0;            // floating props: heave + rock with the waves         // crowd hop height (phase from INSTANCE_CUSTOM.a)

uniform sampler2D detail_alb : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D detail_nrm : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float detail_tex = 0.0;      // 0 = off; >0 triplanar texture detail strength
uniform float detail_tex_scale = 0.25;
uniform float detail_nrm_strength = 0.6;

varying vec3 wpos;
varying vec3 wnrm;
varying vec4 icustom;

float hash(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash(i + vec3(0, 0, 0)), hash(i + vec3(1, 0, 0)), f.x),
				   mix(hash(i + vec3(0, 1, 0)), hash(i + vec3(1, 1, 0)), f.x), f.y),
			   mix(mix(hash(i + vec3(0, 0, 1)), hash(i + vec3(1, 0, 1)), f.x),
				   mix(hash(i + vec3(0, 1, 1)), hash(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	icustom = INSTANCE_CUSTOM;
	if (bob > 0.0) {
		vec3 o = MODEL_MATRIX[3].xyz;
		float ph = TIME * 1.2 + o.x * 0.21 + o.z * 0.17;
		VERTEX.y += sin(ph) * bob;
		float roll = sin(ph * 0.8 + 1.3) * 0.08;
		VERTEX.y += VERTEX.x * roll;
	}
	if (bounce > 0.0) {
		float ph = TIME * (5.5 + INSTANCE_CUSTOM.a * 3.0) + INSTANCE_CUSTOM.a * 6.283;
		float b = abs(sin(ph));
		VERTEX.y += b * bounce;
		VERTEX.xz *= 1.0 + (1.0 - b) * 0.08;
		VERTEX.y *= 1.0 - (1.0 - b) * 0.06;
	}
	if (wind > 0.0) {
		float w = COLOR.a;
		float ph = dot(wpos.xz, vec2(0.11, 0.07)) + TIME * wind_speed;
		float sway = sin(ph) * 0.65 + sin(ph * 2.37 + 1.7) * 0.25 + sin(ph * 6.1 + wpos.y) * 0.1;
		vec3 dir_w = normalize(vec3(1.0, 0.0, 0.35));
		vec3 dir_l = (inverse(MODEL_MATRIX) * vec4(dir_w, 0.0)).xyz;
		VERTEX += dir_l * sway * wind * w * w;
		VERTEX.y += sin(ph * 3.1) * 0.05 * wind * w;
	}
}

void fragment() {
	vec3 base = use_vertex_color ? COLOR.rgb : vec3(1.0);
	base *= tint.rgb;
	if (instance_tint > 0.0) base *= mix(vec3(1.0), icustom.rgb, instance_tint);
	float n = vnoise(wpos * detail_scale) * 0.6 + vnoise(wpos * detail_scale * 3.7) * 0.4;
	base *= 1.0 + (n - 0.5) * 2.0 * detail;
	if (detail_tex > 0.0) {
		vec3 bw = pow(abs(wnrm), vec3(4.0));
		bw /= (bw.x + bw.y + bw.z + 1e-5);
		vec3 p = wpos * detail_tex_scale;
		vec3 t = texture(detail_alb, p.zy).rgb * bw.x + texture(detail_alb, p.xz).rgb * bw.y + texture(detail_alb, p.xy).rgb * bw.z;
		float lum = dot(t, vec3(0.333));
		base *= mix(vec3(1.0), t / max(lum, 0.05) * lum * 1.9, detail_tex);
		vec2 nx = texture(detail_nrm, p.zy).rg * 2.0 - 1.0;
		vec2 ny = texture(detail_nrm, p.xz).rg * 2.0 - 1.0;
		vec2 nz = texture(detail_nrm, p.xy).rg * 2.0 - 1.0;
		vec3 pert = vec3(0.0, nx.y, nx.x) * bw.x + vec3(ny.x, 0.0, ny.y) * bw.y + vec3(nz.x, nz.y, 0.0) * bw.z;
		NORMAL = normalize((VIEW_MATRIX * vec4(normalize(wnrm + pert * detail_nrm_strength * detail_tex), 0.0)).xyz);
	}
	ALBEDO = base;
	ROUGHNESS = roughness_v;
	METALLIC = metallic_v;
	RIM = rim_v;
	RIM_TINT = 0.5;
	EMISSION = base * emission_v;
}
