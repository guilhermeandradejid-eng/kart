shader_type spatial;
render_mode unshaded;
uniform vec4 color : source_color = vec4(1.0, 0.95, 0.6, 1.0);
uniform float strength = 2.5;
uniform float pulse = 0.25;
void fragment() {
	float p = 1.0 - pulse + pulse * (0.5 + 0.5 * sin(TIME * 6.0));
	vec3 c = color.rgb * COLOR.rgb;
	ALBEDO = c * strength * p;
}
