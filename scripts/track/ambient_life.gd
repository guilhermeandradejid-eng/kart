class_name AmbientLife
extends Node3D
## Makes the track feel alive: circling seagulls, butterflies along the jungle
## roadside, fish leaping out of the bay, falling leaves near the camera in the
## jungle, the smoking volcano and drifting hot-air balloons.

var track: Track
var camera: Camera3D
var _gulls: MultiMeshInstance3D
var _gull_data: Array = []         # [centre, radius, height, speed, phase]
var _flies: MultiMeshInstance3D
var _fly_data: Array = []          # [anchor, phase, colour]
var _leaves: GPUParticles3D
var _balloons: Array[Node3D] = []
var _fish_timer := 2.0
var _rng := RandomNumberGenerator.new()
var _t := 0.0


func setup(t: Track, cam: Camera3D) -> void:
	track = t
	camera = cam
	_rng.seed = 42
	_build_gulls()
	_build_butterflies()
	_build_leaves()
	_build_volcano()
	_build_balloons()


func _critter_mat(wing_amp: float, rate: float) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/fx/critter.gdshader")
	m.set_shader_parameter("flap", wing_amp)
	m.set_shader_parameter("rate", rate)
	return m


func _bird_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var white := Color(0.97, 0.97, 0.95)
	var grey := Color(0.45, 0.47, 0.52)
	var tris := [
		# body (diamond)
		[Vector3(0, 0, -0.45), Vector3(0.09, 0, 0), Vector3(0, 0.08, 0), white],
		[Vector3(0, 0, -0.45), Vector3(0, 0.08, 0), Vector3(-0.09, 0, 0), white],
		[Vector3(0, 0.08, 0), Vector3(0.09, 0, 0), Vector3(0, 0, 0.4), white],
		[Vector3(-0.09, 0, 0), Vector3(0, 0.08, 0), Vector3(0, 0, 0.4), white],
		# wings (inner white, tip grey)
		[Vector3(0.08, 0.02, -0.12), Vector3(0.55, 0.02, 0.0), Vector3(0.08, 0.02, 0.12), white],
		[Vector3(0.55, 0.02, 0.0), Vector3(0.95, 0.02, 0.1), Vector3(0.5, 0.02, 0.12), grey],
		[Vector3(-0.08, 0.02, 0.12), Vector3(-0.55, 0.02, 0.0), Vector3(-0.08, 0.02, -0.12), white],
		[Vector3(-0.5, 0.02, 0.12), Vector3(-0.95, 0.02, 0.1), Vector3(-0.55, 0.02, 0.0), grey],
		# tail
		[Vector3(-0.07, 0.01, 0.35), Vector3(0.07, 0.01, 0.35), Vector3(0, 0.01, 0.6), white],
	]
	for t in tris:
		for k in 3:
			st.set_color(t[3])
			st.set_normal(Vector3.UP)
			st.add_vertex(t[k])
	return st.commit()


func _butterfly_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for sx in [-1.0, 1.0]:
		var pts := [Vector3(0, 0, -0.02), Vector3(sx * 0.16, 0, -0.12), Vector3(sx * 0.2, 0, 0.0),
			Vector3(0, 0, 0.02), Vector3(sx * 0.13, 0, 0.11), Vector3(sx * 0.18, 0, 0.0)]
		for tri in [[0, 1, 2], [3, 5, 4]]:
			for k in tri:
				st.set_color(Color.WHITE)
				st.set_normal(Vector3.UP)
				st.add_vertex(pts[k])
	return st.commit()


func _build_gulls() -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.mesh = _bird_mesh()
	var n := 26
	mm.instance_count = n
	var st := track.transform_at(track.data.start_s, 0.0, 0.0)
	for i in n:
		var c := st.origin + Vector3(_rng.randf_range(-160, 160), 0, _rng.randf_range(-20, 90))
		_gull_data.append([c, _rng.randf_range(12, 40), _rng.randf_range(14, 34), _rng.randf_range(0.18, 0.4) * (1 if _rng.randf() < 0.5 else -1),
			_rng.randf() * TAU])
		mm.set_instance_custom_data(i, Color(1, 1, 1, _rng.randf()))
	_gulls = MultiMeshInstance3D.new()
	_gulls.multimesh = mm
	_gulls.material_override = _critter_mat(0.55, 9.0)
	_gulls.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	add_child(_gulls)


func _build_butterflies() -> void:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_custom_data = true
	mm.use_colors = true
	mm.mesh = _butterfly_mesh()
	var n := 90
	mm.instance_count = n
	var palette := [Color("ff8a1f"), Color("ffd23f"), Color("5ee0ff"), Color("ff5fa2"), Color("9b4be0"), Color("ffffff")]
	for i in n:
		var s := _rng.randf() * track.length
		var fr := track.frame_at(s)
		var side := -1.0 if _rng.randf() < 0.5 else 1.0
		var anchor: Vector3 = fr.p + fr.r * side * (fr.w * 0.5 + _rng.randf_range(4.0, 12.0)) + Vector3.UP * _rng.randf_range(0.6, 2.2)
		_fly_data.append([anchor, _rng.randf() * TAU])
		mm.set_instance_color(i, palette[i % palette.size()])
		mm.set_instance_custom_data(i, Color(1, 1, 1, _rng.randf()))
	_flies = MultiMeshInstance3D.new()
	_flies.multimesh = mm
	var m := _critter_mat(1.0, 22.0)
	m.set_shader_parameter("use_instance_color", true)
	_flies.material_override = m
	_flies.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_flies)


func _build_leaves() -> void:
	_leaves = Fx.make_particles({"amount": 70, "lifetime": 6.0, "dir": Vector3.DOWN, "spread": 30.0, "vmin": 0.4, "vmax": 1.0,
		"gravity": Vector3(0.6, -0.9, 0.2), "damp": 0.4, "tex": Fx.tex_confetti, "blend": "mix", "box": Vector3(26, 2, 26),
		"size": Vector2(0.16, 0.24), "spin_min": -200.0, "spin_max": 200.0, "angle_max": 360.0, "hue_var": 0.05,
		"ramp": [[0.0, Color(0.45, 0.75, 0.25, 0.0)], [0.1, Color(0.5, 0.78, 0.25, 1.0)], [0.8, Color(0.85, 0.6, 0.2, 1.0)], [1.0, Color(0.8, 0.5, 0.2, 0.0)]]})
	_leaves.visibility_aabb = AABB(Vector3(-40, -30, -40), Vector3(80, 60, 80))
	add_child(_leaves)
	_leaves.emitting = false


func _build_volcano() -> void:
	if not track.data.has("volcano"):
		return
	var p := Track._v(track.data.volcano)
	var smoke := Fx.make_particles({"amount": 40, "lifetime": 14.0, "dir": Vector3(0.2, 1, 0), "spread": 12.0, "vmin": 6.0,
		"vmax": 10.0, "gravity": Vector3(2.5, 0.5, 0), "damp": 0.3, "tex": Fx.tex_puff, "blend": "mix", "radius": 20.0,
		"size": Vector2(55, 55), "scale_curve": [[0.0, 0.4], [1.0, 2.6]], "spin_min": -10.0, "spin_max": 10.0,
		"ramp": [[0.0, Color(0.55, 0.52, 0.5, 0.0)], [0.1, Color(0.6, 0.57, 0.55, 0.7)], [1.0, Color(0.85, 0.85, 0.88, 0.0)]]})
	smoke.visibility_aabb = AABB(Vector3(-300, -50, -300), Vector3(600, 700, 600))
	add_child(smoke)
	smoke.global_position = p
	smoke.emitting = true
	var glow := OmniLight3D.new()
	glow.light_color = Color(1.0, 0.45, 0.15)
	glow.light_energy = 6.0
	glow.omni_range = 120.0
	add_child(glow)
	glow.global_position = p + Vector3.UP * 10.0


func _build_balloons() -> void:
	var cols := [[Color("ef3b36"), Color("ffd23f")], [Color("1fb7c9"), Color("ffffff")], [Color("9b4be0"), Color("ff8a1f")]]
	for i in 3:
		var b := Node3D.new()
		var env := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 6.0
		sm.height = 14.0
		sm.radial_segments = 24
		sm.rings = 12
		env.mesh = sm
		var mat := ShaderMaterial.new()
		mat.shader = load("res://shaders/fx/balloon.gdshader")
		mat.set_shader_parameter("color_a", cols[i][0])
		mat.set_shader_parameter("color_b", cols[i][1])
		env.material_override = mat
		b.add_child(env)
		var basket := MeshInstance3D.new()
		var bx := BoxMesh.new()
		bx.size = Vector3(2.2, 1.6, 2.2)
		basket.mesh = bx
		basket.position.y = -9.5
		basket.material_override = Mats.std(Color("8a5a33"), 0.9)
		b.add_child(basket)
		add_child(b)
		var st := track.transform_at(track.length * (0.15 + 0.3 * i), 0.0, 0.0)
		b.global_position = st.origin + Vector3(_rng.randf_range(-120, 120), _rng.randf_range(60, 95), _rng.randf_range(-120, 120))
		_balloons.append(b)


func _process(dt: float) -> void:
	_t += dt
	var mm := _gulls.multimesh
	for i in _gull_data.size():
		var g: Array = _gull_data[i]
		var a: float = g[4] + _t * float(g[3])
		var c: Vector3 = g[0]
		var r: float = g[1]
		var p := c + Vector3(cos(a) * r, float(g[2]) + sin(a * 2.0 + i) * 2.0, sin(a) * r)
		var tangent := Vector3(-sin(a), 0.0, cos(a)) * signf(float(g[3]))
		var bank := -signf(float(g[3])) * 0.35
		var basis := Basis.looking_at(tangent, Vector3.UP).rotated(tangent.normalized(), bank)
		mm.set_instance_transform(i, Transform3D(basis.scaled(Vector3.ONE * 1.4), p))
	var fm := _flies.multimesh
	for i in _fly_data.size():
		var f: Array = _fly_data[i]
		var ph: float = f[1]
		var anchor: Vector3 = f[0]
		var p := anchor + Vector3(sin(_t * 0.7 + ph) * 1.6, sin(_t * 1.9 + ph * 2.0) * 0.5, cos(_t * 0.53 + ph * 1.3) * 1.6)
		var d := Vector3(cos(_t * 0.7 + ph), 0.2, -sin(_t * 0.53 + ph * 1.3)).normalized()
		fm.set_instance_transform(i, Transform3D(Basis.looking_at(d, Vector3.UP).scaled(Vector3.ONE * 1.5), p))
	for i in _balloons.size():
		var b := _balloons[i]
		b.global_position += Vector3(1.0, sin(_t * 0.2 + i) * 0.3, 0.4) * dt * 1.6
		b.rotation.y += dt * 0.05
	if camera:
		_leaves.global_position = camera.global_position + Vector3.UP * 9.0 - camera.global_basis.z * 8.0
		var loc := track.locate(camera.global_position)
		var r := fposmod(loc.s - float(track.data.start_s), track.length)
		_leaves.emitting = r > 470.0 and r < 1120.0 and not track.has_tag(loc.s, "tunnel")
		_fish_timer -= dt
		if _fish_timer <= 0.0:
			_fish_timer = _rng.randf_range(1.5, 4.0)
			_spawn_fish()


func _spawn_fish() -> void:
	var cam := camera.global_position
	var fwd := -camera.global_basis.z
	for tries in 12:
		var p := cam + fwd * _rng.randf_range(25, 90) + camera.global_basis.x * _rng.randf_range(-50, 50)
		p.y = track.water_level
		var space := get_world_3d().direct_space_state
		var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 40.0, p + Vector3.DOWN * 3.0, 1)
		var hit := space.intersect_ray(q)
		if hit.is_empty() or (hit.position as Vector3).y < track.water_level - 1.2:
			_jump_fish(p)
			return


func _jump_fish(p: Vector3) -> void:
	var fish := MeshInstance3D.new()
	var cm := CapsuleMesh.new()
	cm.radius = 0.16
	cm.height = 0.8
	fish.mesh = cm
	fish.material_override = Mats.std(Color("ff9a3c"), 0.25, 0.3, {"rim": 0.4})
	add_child(fish)
	var dir := Vector3(_rng.randf_range(-1, 1), 0, _rng.randf_range(-1, 1)).normalized()
	fish.global_position = p
	Fx.burst("splash", p, Vector3.UP, Color.WHITE, 0.35)
	var dur := 0.9
	var tw := fish.create_tween()
	tw.tween_method(func(u: float):
		fish.global_position = p + dir * u * 3.0 + Vector3.UP * (sin(u * PI) * 2.2)
		fish.global_basis = Basis.looking_at(dir + Vector3.UP * cos(u * PI) * 1.2, Vector3.UP).rotated(dir.cross(Vector3.UP).normalized(), PI / 2),
		0.0, 1.0, dur)
	tw.tween_callback(func():
		Fx.burst("splash", fish.global_position, Vector3.UP, Color.WHITE, 0.3)
		fish.queue_free())
