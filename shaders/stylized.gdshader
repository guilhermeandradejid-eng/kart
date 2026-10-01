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

varying vec3 wpos;
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
	icustom = INSTANCE_CUSTOM;
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
	ALBEDO = base;
	ROUGHNESS = roughness_v;
	METALLIC = metallic_v;
	RIM = rim_v;
	RIM_TINT = 0.5;
	EMISSION = base * emission_v;
}
