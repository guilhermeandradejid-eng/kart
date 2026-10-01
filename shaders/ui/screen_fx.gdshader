shader_type canvas_item;
// Full-screen post pass over the 3D view: radial "speed" blur toward the
// centre while boosting, chromatic aberration pulses on impacts, vignette,
// and anime speed lines streaming from the edges.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform float blur = 0.0;         // 0..1
uniform float aberration = 0.0;   // 0..1
uniform float vignette = 0.35;
uniform float lines = 0.0;        // 0..1
uniform vec4 line_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform vec4 tint : source_color = vec4(1.0, 1.0, 1.0, 0.0);

float hash(float n) { return fract(sin(n) * 43758.5453123); }

void fragment() {
	vec2 uv = SCREEN_UV;
	vec2 c = uv - vec2(0.5, 0.52);
	float r = length(c);
	vec3 col = vec3(0.0);
	if (blur > 0.001) {
		float acc = 0.0;
		for (int i = 0; i < 8; i++) {
			float t = float(i) / 7.0;
			float w = 1.0 - t * 0.6;
			vec2 o = c * t * blur * 0.06 * smoothstep(0.12, 0.6, r);
			col += texture(screen_tex, uv - o).rgb * w;
			acc += w;
		}
		col /= acc;
	} else {
		col = texture(screen_tex, uv).rgb;
	}
	if (aberration > 0.001) {
		vec2 o = c * aberration * 0.018;
		col.r = texture(screen_tex, uv + o).r;
		col.b = texture(screen_tex, uv - o).b;
	}
	// speed lines: angular noise streaks near the screen edge
	if (lines > 0.001) {
		float a = atan(c.y, c.x);
		float seg = floor(a * 38.0);
		float h = hash(seg + floor(TIME * 18.0) * 7.13);
		float streak = step(0.72, h) * smoothstep(0.33, 0.62, r) * lines;
		float along = fract(r * 3.0 - TIME * 6.0 - h * 4.0);
		streak *= smoothstep(0.0, 0.3, along) * smoothstep(1.0, 0.6, along);
		col = mix(col, line_color.rgb, streak * 0.55);
	}
	float v = smoothstep(0.85, 0.25, r);
	col *= mix(1.0, v, vignette);
	col = mix(col, tint.rgb, tint.a);
	COLOR = vec4(col, 1.0);
}
