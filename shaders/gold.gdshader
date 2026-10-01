shader_type spatial;
// Golden collectible: warm metal, twinkling sparkles, soft self glow.
render_mode diffuse_burley, specular_schlick_ggx;
uniform vec4 gold : source_color = vec4(1.0, 0.76, 0.25, 1.0);
uniform float use_vcol = 1.0;
varying vec3 opos;
void vertex() { opos = VERTEX; }
float hash(vec3 p) { return fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
void fragment() {
	vec3 c = mix(gold.rgb, COLOR.rgb * gold.rgb * 1.3, use_vcol);
	vec3 cell = floor(opos * 40.0);
	float h = hash(cell);
	float tw = pow(max(sin(TIME * (3.0 + h * 5.0) + h * 20.0), 0.0), 24.0) * step(0.93, h);
	float fres = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	ALBEDO = c;
	METALLIC = 1.0;
	ROUGHNESS = 0.22;
	EMISSION = c * (0.18 + fres * 0.6) + vec3(1.0, 0.95, 0.8) * tw * 4.0;
}
