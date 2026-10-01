class_name ColorGrade
extends RefCounted
## Builds 3D colour-grading LUTs in code (Environment.adjustment_color_correction).
## "tropical": the CTR Nitro-Fueled look — saturated, warm golden highlights,
## slightly teal shadows, gentle S-curve, greens/blues pushed toward candy.

static var _cache := {}


static func lut(style := "tropical", size := 32) -> Texture3D:
	var key := "%s_%d" % [style, size]
	if _cache.has(key):
		return _cache[key]
	var images: Array[Image] = []
	for b in size:
		var img := Image.create(size, size, false, Image.FORMAT_RGB8)
		for g in size:
			for r in size:
				var c := Color(r / float(size - 1), g / float(size - 1), b / float(size - 1))
				img.set_pixel(r, g, _grade(c, style))
		images.append(img)
	var tex := ImageTexture3D.new()
	tex.create(Image.FORMAT_RGB8, size, size, size, false, images)
	_cache[key] = tex
	return tex


static func _s_curve(x: float, amount: float) -> float:
	var s := x * x * (3.0 - 2.0 * x)
	return lerpf(x, s, amount)


static func _grade(c: Color, style: String) -> Color:
	var lum := c.r * 0.2126 + c.g * 0.7152 + c.b * 0.0722
	var out := c
	match style:
		"tropical":
			# saturation (stronger on mid-saturated colours, protects skin/fur)
			var sat := 1.22
			out = Color(lerpf(lum, out.r, sat), lerpf(lum, out.g, sat), lerpf(lum, out.b, sat))
			# split toning: teal shadows, golden highlights
			var sh := 1.0 - smoothstep(0.0, 0.45, lum)
			var hi := smoothstep(0.5, 1.0, lum)
			out = Color(out.r - 0.025 * sh + 0.045 * hi, out.g + 0.01 * sh + 0.025 * hi, out.b + 0.04 * sh - 0.03 * hi)
			# candy greens and turquoise water
			if out.g > out.r and out.g > out.b:
				out.g += 0.03 * (out.g - maxf(out.r, out.b))
			if out.b > out.r and out.g > out.r:
				out.b += 0.03 * (minf(out.g, out.b) - out.r)
			out = Color(_s_curve(clampf(out.r, 0, 1), 0.28), _s_curve(clampf(out.g, 0, 1), 0.28), _s_curve(clampf(out.b, 0, 1), 0.28))
			# lift blacks a touch (painted look, never crushed)
			out = Color(0.025 + out.r * 0.975, 0.025 + out.g * 0.975, 0.035 + out.b * 0.965)
		"sunset":
			var sat2 := 1.12
			out = Color(lerpf(lum, out.r, sat2), lerpf(lum, out.g, sat2), lerpf(lum, out.b, sat2))
			out = Color(out.r * 1.06 + 0.02, out.g * 0.99, out.b * 0.92 + 0.03)
			out = Color(_s_curve(clampf(out.r, 0, 1), 0.2), _s_curve(clampf(out.g, 0, 1), 0.2), _s_curve(clampf(out.b, 0, 1), 0.2))
	return Color(clampf(out.r, 0, 1), clampf(out.g, 0, 1), clampf(out.b, 0, 1))


## Apply the shared "Turbo Turma" post stack to an Environment.
static func apply(e: Environment, quality: String, style := "tropical") -> void:
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	e.tonemap_exposure = 1.08
	e.tonemap_white = 5.0
	e.glow_enabled = true
	e.glow_normalized = false
	e.glow_intensity = 0.75
	e.glow_strength = 1.0
	e.glow_bloom = 0.07
	e.glow_hdr_threshold = 0.95
	e.glow_hdr_scale = 2.2
	e.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	for i in 7:
		e.set_glow_level(i, 1.0 if i in [1, 2, 3, 4] else (0.5 if i == 5 else 0.0))
	e.ssao_enabled = quality != "low"
	e.ssao_radius = 1.4
	e.ssao_intensity = 2.2
	e.ssao_power = 1.6
	e.ssao_detail = 0.6
	e.ssao_light_affect = 0.15
	e.ssil_enabled = quality == "high" or quality == "ultra"
	e.ssil_radius = 4.0
	e.ssil_intensity = 0.8
	e.ssr_enabled = quality == "ultra"
	e.sdfgi_enabled = quality == "ultra"
	if e.sdfgi_enabled:
		e.sdfgi_use_occlusion = true
		e.sdfgi_cascades = 5
		e.sdfgi_min_cell_size = 0.3
		e.sdfgi_energy = 0.9
	e.adjustment_enabled = true
	e.adjustment_brightness = 1.0
	e.adjustment_contrast = 1.0
	e.adjustment_saturation = 1.0
	e.adjustment_color_correction = lut(style)
