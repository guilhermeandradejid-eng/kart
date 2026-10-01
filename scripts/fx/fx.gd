extends Node
## One-shot VFX library (autoload "Fx"). Everything is procedural: particle
## textures are painted into Images at start-up, materials are built in code.
## burst(kind, position, [normal], [color]) spawns a self-freeing effect.

var tex_soft: Texture2D
var tex_spark: Texture2D
var tex_star: Texture2D
var tex_puff: Texture2D
var tex_ring: Texture2D
var tex_confetti: Texture2D
var _mats := {}
var _quad_cache := {}


func _ready() -> void:
	tex_soft = _radial(64, 2.2)
	tex_spark = _spark_tex()
	tex_star = _star_tex()
	tex_puff = _puff_tex()
	tex_ring = _ring_tex()
	tex_confetti = _rect_tex()


# ---------------------------------------------------------------- textures

func _radial(size: int, power: float) -> ImageTexture:
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	var c := (size - 1) / 2.0
	for y in size:
		for x in size:
			var d := Vector2(x - c, y - c).length() / c
			var a := pow(clampf(1.0 - d, 0.0, 1.0), power)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _spark_tex() -> ImageTexture:
	var w := 16
	var h := 64
	var img := Image.create(w, h, false, Image.FORMAT_RGBA8)
	for y in h:
		for x in w:
			var dx := absf(x - (w - 1) / 2.0) / (w / 2.0)
			var dy := absf(y - (h - 1) / 2.0) / (h / 2.0)
			var a := pow(clampf(1.0 - dx, 0, 1), 1.5) * pow(clampf(1.0 - dy, 0, 1), 0.8)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _star_tex() -> ImageTexture:
	var s := 64
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	var c := (s - 1) / 2.0
	for y in s:
		for x in s:
			var p := Vector2(x - c, y - c) / c
			var ang := p.angle()
			var r := 0.55 + 0.45 * pow(absf(cos(ang * 2.5)), 6.0)
			var d := p.length() / r
			var a := clampf((1.0 - d) * 6.0, 0.0, 1.0)
			var core := clampf(1.0 - p.length() * 2.5, 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1 - core * 0.0, maxf(a, core)))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _puff_tex() -> ImageTexture:
	var s := 64
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	var n := FastNoiseLite.new()
	n.frequency = 0.08
	var c := (s - 1) / 2.0
	for y in s:
		for x in s:
			var d := Vector2(x - c, y - c).length() / c
			var v := n.get_noise_2d(x, y) * 0.35
			var a := clampf(smoothstep(1.0, 0.45, d + v), 0.0, 1.0)
			var shade := 0.8 + 0.2 * clampf(1.0 - Vector2(x - c * 0.7, y - c * 0.7).length() / c, 0, 1)
			img.set_pixel(x, y, Color(shade, shade, shade, a))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _ring_tex() -> ImageTexture:
	var s := 64
	var img := Image.create(s, s, false, Image.FORMAT_RGBA8)
	var c := (s - 1) / 2.0
	for y in s:
		for x in s:
			var d := Vector2(x - c, y - c).length() / c
			var a := clampf(1.0 - absf(d - 0.8) * 8.0, 0.0, 1.0)
			img.set_pixel(x, y, Color(1, 1, 1, a))
	img.generate_mipmaps()
	return ImageTexture.create_from_image(img)


func _rect_tex() -> ImageTexture:
	var img := Image.create(8, 8, false, Image.FORMAT_RGBA8)
	img.fill(Color.WHITE)
	return ImageTexture.create_from_image(img)


# ---------------------------------------------------------------- materials

## Billboard particle material. mode: "add" | "mix"; align: stretch along velocity.
func particle_mat(tex: Texture2D, mode := "add", align := false, emission := 1.0) -> StandardMaterial3D:
	var key := "%s|%s|%s|%s" % [tex.get_instance_id(), mode, align, emission]
	if _mats.has(key):
		return _mats[key]
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_texture = tex
	m.vertex_color_use_as_albedo = true
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.blend_mode = BaseMaterial3D.BLEND_MODE_ADD if mode == "add" else BaseMaterial3D.BLEND_MODE_MIX
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES if not align else BaseMaterial3D.BILLBOARD_FIXED_Y
	m.billboard_keep_scale = true
	m.depth_draw_mode = BaseMaterial3D.DEPTH_DRAW_DISABLED
	m.no_depth_test = false
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	if emission != 1.0:
		m.albedo_color = Color(emission, emission, emission, 1.0)
	_mats[key] = m
	return m


func quad(size: Vector2, mat: Material) -> QuadMesh:
	var q := QuadMesh.new()
	q.size = size
	q.material = mat
	return q


func gradient(stops: Array) -> GradientTexture1D:
	var g := Gradient.new()
	var offs := PackedFloat32Array()
	var cols := PackedColorArray()
	for st in stops:
		offs.append(st[0])
		cols.append(st[1])
	g.offsets = offs
	g.colors = cols
	var t := GradientTexture1D.new()
	t.gradient = g
	return t


func curve(points: Array) -> CurveTexture:
	var c := Curve.new()
	for p in points:
		c.add_point(Vector2(p[0], p[1]))
	var t := CurveTexture.new()
	t.curve = c
	return t


## Configurable GPU particle system factory used by karts and one-shots.
func make_particles(o: Dictionary) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.amount = o.get("amount", 16)
	p.lifetime = o.get("lifetime", 0.6)
	p.one_shot = o.get("one_shot", false)
	p.explosiveness = o.get("explosiveness", 0.0)
	p.randomness = o.get("randomness", 0.3)
	p.local_coords = o.get("local", false)
	p.fixed_fps = 60
	p.visibility_aabb = AABB(Vector3(-8, -8, -8), Vector3(16, 16, 16))
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var pm := ParticleProcessMaterial.new()
	pm.direction = o.get("dir", Vector3.UP)
	pm.spread = o.get("spread", 30.0)
	pm.initial_velocity_min = o.get("vmin", 1.0)
	pm.initial_velocity_max = o.get("vmax", 3.0)
	pm.gravity = o.get("gravity", Vector3(0, -9.8, 0))
	pm.damping_min = o.get("damp", 0.0)
	pm.damping_max = o.get("damp", 0.0)
	pm.scale_min = o.get("smin", 0.5)
	pm.scale_max = o.get("smax", 1.0)
	if o.has("scale_curve"):
		pm.scale_curve = curve(o.scale_curve)
	if o.has("ramp"):
		pm.color_ramp = gradient(o.ramp)
	if o.has("color"):
		pm.color = o.color
	pm.emission_shape = o.get("shape", ParticleProcessMaterial.EMISSION_SHAPE_SPHERE)
	pm.emission_sphere_radius = o.get("radius", 0.1)
	if o.has("box"):
		pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
		pm.emission_box_extents = o.box
	if o.has("ring"):
		pm.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
		pm.emission_ring_axis = o.get("ring_axis", Vector3.UP)
		pm.emission_ring_radius = o.ring
		pm.emission_ring_inner_radius = o.ring * 0.8
		pm.emission_ring_height = 0.05
	if o.get("align", false):
		pm.particle_flag_align_y = true
	pm.angle_min = o.get("angle_min", 0.0)
	pm.angle_max = o.get("angle_max", 0.0)
	pm.angular_velocity_min = o.get("spin_min", 0.0)
	pm.angular_velocity_max = o.get("spin_max", 0.0)
	if o.has("orbit"):
		pm.orbit_velocity_min = o.orbit
		pm.orbit_velocity_max = o.orbit
	if o.has("radial"):
		pm.radial_velocity_min = o.radial
		pm.radial_velocity_max = o.radial
	if o.has("hue_var"):
		pm.hue_variation_min = -o.hue_var
		pm.hue_variation_max = o.hue_var
	p.process_material = pm
	var tex: Texture2D = o.get("tex", tex_soft)
	# streaks: Y aligned to velocity + fixed-Y billboard
	var mat := particle_mat(tex, o.get("blend", "add"), o.get("align", false), o.get("emission", 1.0))
	p.draw_pass_1 = quad(o.get("size", Vector2(0.3, 0.3)), mat)
	return p


# ---------------------------------------------------------------- one-shots

func burst(kind: String, pos: Vector3, normal := Vector3.UP, color := Color.WHITE, scale := 1.0) -> void:
	var scene := get_tree().current_scene
	if scene == null:
		return
	var p: GPUParticles3D
	match kind:
		"sparks":
			p = make_particles({"amount": 28, "lifetime": 0.45, "one_shot": true, "explosiveness": 0.95, "dir": normal,
				"spread": 70.0, "vmin": 5.0, "vmax": 13.0, "gravity": Vector3(0, -22, 0), "tex": tex_spark,
				"size": Vector2(0.06, 0.3) * scale, "align": true,
				"ramp": [[0.0, Color(1, 1, 0.8, 1)], [0.4, Color(1, 0.7, 0.2, 1)], [1.0, Color(1, 0.3, 0.05, 0)]]})
		"dust":
			p = make_particles({"amount": 22, "lifetime": 0.9, "one_shot": true, "explosiveness": 0.9,
				"ring": 1.0 * scale, "dir": Vector3.UP, "spread": 80.0, "vmin": 1.0, "vmax": 3.5, "radial": 3.5,
				"gravity": Vector3(0, 0.6, 0), "damp": 3.0, "tex": tex_puff, "blend": "mix", "size": Vector2(0.9, 0.9) * scale,
				"scale_curve": [[0.0, 0.4], [0.3, 1.0], [1.0, 1.3]], "spin_min": -60.0, "spin_max": 60.0,
				"ramp": [[0.0, Color(color, 0.85)], [1.0, Color(color, 0.0)]]})
		"stars":
			p = make_particles({"amount": 10, "lifetime": 0.8, "one_shot": true, "explosiveness": 1.0, "spread": 180.0,
				"vmin": 3.0, "vmax": 6.0, "gravity": Vector3(0, -4, 0), "damp": 2.0, "tex": tex_star, "size": Vector2(0.45, 0.45) * scale,
				"spin_min": -180.0, "spin_max": 180.0, "hue_var": 0.08,
				"ramp": [[0.0, Color(1, 0.95, 0.4, 1)], [0.8, Color(1, 0.8, 0.2, 1)], [1.0, Color(1, 0.6, 0.1, 0)]]})
		"shatter":
			p = make_particles({"amount": 36, "lifetime": 0.9, "one_shot": true, "explosiveness": 1.0, "spread": 180.0,
				"vmin": 4.0, "vmax": 10.0, "gravity": Vector3(0, -14, 0), "tex": tex_confetti, "size": Vector2(0.14, 0.14) * scale,
				"spin_min": -400.0, "spin_max": 400.0, "hue_var": 0.5, "angle_max": 360.0,
				"ramp": [[0.0, Color(0.6, 0.9, 1.0, 1)], [0.7, Color(1, 0.6, 1.0, 1)], [1.0, Color(1, 1, 1, 0)]]})
			_flash(pos, Color(1, 1, 1), 5.0 * scale, 0.25)
		"pickup":
			p = make_particles({"amount": 14, "lifetime": 0.6, "one_shot": true, "explosiveness": 1.0, "spread": 180.0,
				"vmin": 2.0, "vmax": 5.0, "gravity": Vector3(0, 3, 0), "damp": 4.0, "tex": tex_star, "size": Vector2(0.3, 0.3) * scale,
				"ramp": [[0.0, Color(1, 0.9, 0.4, 1)], [1.0, Color(1, 0.7, 0.2, 0)]]})
		"explosion":
			p = make_particles({"amount": 40, "lifetime": 1.0, "one_shot": true, "explosiveness": 1.0, "spread": 180.0,
				"vmin": 4.0, "vmax": 12.0, "gravity": Vector3(0, 3, 0), "damp": 5.0, "tex": tex_puff, "blend": "mix",
				"size": Vector2(2.2, 2.2) * scale, "scale_curve": [[0.0, 0.3], [0.2, 1.0], [1.0, 1.4]], "spin_min": -90.0, "spin_max": 90.0,
				"ramp": [[0.0, Color(1, 0.95, 0.6, 1)], [0.15, Color(1, 0.55, 0.1, 1)], [0.4, Color(0.35, 0.3, 0.3, 0.9)], [1.0, Color(0.3, 0.3, 0.3, 0)]]})
			burst("sparks", pos, Vector3.UP, Color.WHITE, 1.6)
			_flash(pos, Color(1, 0.6, 0.2), 14.0 * scale, 0.35)
		"splash":
			p = make_particles({"amount": 40, "lifetime": 1.1, "one_shot": true, "explosiveness": 0.95, "dir": Vector3.UP,
				"spread": 25.0, "vmin": 6.0, "vmax": 12.0, "gravity": Vector3(0, -22, 0), "tex": tex_soft,
				"size": Vector2(0.45, 0.45) * scale, "blend": "mix",
				"ramp": [[0.0, Color(0.9, 1, 1, 0.95)], [1.0, Color(0.7, 0.95, 1, 0)]]})
		"confetti":
			p = make_particles({"amount": 160, "lifetime": 3.2, "one_shot": true, "explosiveness": 0.85, "dir": Vector3.UP,
				"spread": 55.0, "vmin": 8.0, "vmax": 16.0, "gravity": Vector3(0, -6, 0), "damp": 1.6, "tex": tex_confetti,
				"size": Vector2(0.16, 0.26) * scale, "spin_min": -720.0, "spin_max": 720.0, "angle_max": 360.0, "hue_var": 0.5,
				"ramp": [[0.0, Color(1, 0.3, 0.3, 1)], [0.9, Color(0.3, 0.8, 1.0, 1)], [1.0, Color(1, 1, 1, 0)]]})
		"poof":
			p = make_particles({"amount": 18, "lifetime": 0.7, "one_shot": true, "explosiveness": 1.0, "spread": 180.0,
				"vmin": 2.0, "vmax": 4.0, "gravity": Vector3.ZERO, "damp": 5.0, "tex": tex_puff, "blend": "mix",
				"size": Vector2(1.0, 1.0) * scale, "scale_curve": [[0.0, 0.5], [1.0, 1.3]],
				"ramp": [[0.0, Color(1, 1, 1, 0.9)], [1.0, Color(1, 1, 1, 0)]]})
			burst("stars", pos, Vector3.UP, Color.WHITE, scale)
		"ring":
			p = make_particles({"amount": 1, "lifetime": 0.45, "one_shot": true, "explosiveness": 1.0, "spread": 0.0,
				"vmin": 0.0, "vmax": 0.0, "gravity": Vector3.ZERO, "tex": tex_ring, "size": Vector2(3.0, 3.0) * scale,
				"scale_curve": [[0.0, 0.2], [1.0, 1.6]],
				"ramp": [[0.0, Color(color, 1)], [1.0, Color(color, 0)]]})
		_:
			return
	scene.add_child(p)
	p.global_position = pos
	p.emitting = true
	p.finished.connect(p.queue_free)


func _flash(pos: Vector3, color: Color, energy: float, time: float) -> void:
	var l := OmniLight3D.new()
	l.light_color = color
	l.light_energy = energy
	l.omni_range = 7.0
	l.shadow_enabled = false
	get_tree().current_scene.add_child(l)
	l.global_position = pos + Vector3.UP * 0.8
	var tw := l.create_tween()
	tw.tween_property(l, "light_energy", 0.0, time).set_ease(Tween.EASE_OUT)
	tw.tween_callback(l.queue_free)
