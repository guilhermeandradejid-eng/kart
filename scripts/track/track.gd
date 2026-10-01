class_name Track
extends Node3D
## Loads a track built by tools/blender/track.py: the .glb (visuals + "-colonly"
## collision named by surface) and the .json gameplay data (centreline samples,
## grid, item boxes, pads, shells, decor, scatter). Provides progress queries
## used by the race, AI and camera.

signal built

var id := "coconut_bay"
var data := {}
var length := 1.0
var pos := PackedVector3Array()
var fwd := PackedVector3Array()
var right := PackedVector3Array()
var upv := PackedVector3Array()
var width := PackedFloat32Array()
var svals := PackedFloat32Array()
var curv := PackedFloat32Array()
var tags: Array = []
var n := 0
var step := 2.0
var water_level := 0.0
var sun: DirectionalLight3D
var env: WorldEnvironment
var item_boxes: Array = []
var _tunnel_ranges: Array = []


func load_track(track_id: String, with_decor := true) -> void:
	id = track_id
	var f := FileAccess.open("res://data/tracks/%s.json" % id, FileAccess.READ)
	data = JSON.parse_string(f.get_as_text())
	length = data.length
	water_level = data.get("water_level", 0.0)
	for s in data.samples:
		pos.append(_v(s.p))
		fwd.append(_v(s.f))
		right.append(_v(s.r))
		upv.append(_v(s.u))
		width.append(s.w)
		svals.append(s.s)
		curv.append(s.c)
		tags.append(s.t)
	n = pos.size()
	step = length / n
	for i in n:
		if "tunnel" in tags[i]:
			_tunnel_ranges.append(svals[i])
	_build_geometry()
	_build_environment()
	_spawn_gameplay()
	if with_decor:
		_spawn_decor()
	built.emit()


static func _v(a: Array) -> Vector3:
	return Vector3(a[0], a[1], a[2])


static func _basis(d: Dictionary) -> Basis:
	return Basis(_v(d.x), _v(d.y), _v(d.z)).orthonormalized()


# ---------------------------------------------------------------- geometry

func _build_geometry() -> void:
	var ps := load("res://assets/models/track/%s.glb" % id) as PackedScene
	var glb := ps.instantiate()
	glb.name = "Geometry"
	add_child(glb)
	Mats.apply(glb, "world")
	for body in glb.find_children("*", "StaticBody3D", true, false):
		var sb := body as StaticBody3D
		var nm := String(sb.name).to_lower()
		for s in ["road", "wood", "grass", "sand", "wall"]:
			if nm.begins_with(s):
				sb.set_meta("surface", s)
		sb.collision_layer = 1
		sb.collision_mask = 0
		for cs in sb.get_children():
			if cs is CollisionShape3D and (cs as CollisionShape3D).shape is ConcavePolygonShape3D:
				((cs as CollisionShape3D).shape as ConcavePolygonShape3D).backface_collision = true
	for mi in glb.find_children("*", "MeshInstance3D", true, false):
		var m := mi as MeshInstance3D
		if m.name.begins_with("Water"):
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if m.name.begins_with("Terrain"):
			m.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON


func _build_environment() -> void:
	env = WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/track/sky.gdshader")
	sm.set_shader_parameter("noise_tex", Mats.noise())
	sky.sky_material = sm
	sky.radiance_size = Sky.RADIANCE_SIZE_256
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.ambient_light_energy = 1.0
	e.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	e.tonemap_exposure = 1.05
	e.tonemap_white = 6.0
	e.glow_enabled = true
	e.glow_intensity = 0.55
	e.glow_strength = 0.9
	e.glow_bloom = 0.04
	e.glow_hdr_threshold = 1.1
	e.glow_blend_mode = Environment.GLOW_BLEND_MODE_SOFTLIGHT
	e.ssao_enabled = Game.settings.quality != "low"
	e.ssao_radius = 1.6
	e.ssao_intensity = 1.4
	e.ssil_enabled = Game.settings.quality == "high"
	e.fog_enabled = true
	e.fog_mode = Environment.FOG_MODE_DEPTH
	e.fog_light_color = Color(0.68, 0.84, 0.98)
	e.fog_depth_begin = 160.0
	e.fog_depth_end = 900.0
	e.fog_density = 0.6
	e.fog_sky_affect = 0.25
	e.adjustment_enabled = true
	e.adjustment_saturation = 1.12
	e.adjustment_contrast = 1.05
	env.environment = e
	add_child(env)
	sun = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.light_color = Color(1.0, 0.95, 0.86)
	sun.light_energy = 1.35
	sun.rotation_degrees = Vector3(-52, -38, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 140.0
	sun.shadow_blur = 1.2
	sun.shadow_bias = 0.04
	add_child(sun)


# ---------------------------------------------------------------- gameplay objects

func _spawn_gameplay() -> void:
	var gp := Node3D.new()
	gp.name = "Gameplay"
	add_child(gp)
	for b in data.item_boxes:
		var box := ItemBox.new()
		gp.add_child(box)
		box.global_transform = Transform3D(_basis(b), _v(b.p))
		item_boxes.append(box)
	for p in data.boost_pads:
		var pad := BoostPad.new()
		gp.add_child(pad)
		pad.global_transform = Transform3D(_basis(p), _v(p.p))
	for s in data.shells:
		var sh := ShellPickup.new()
		gp.add_child(sh)
		sh.global_transform = Transform3D(_basis(s), _v(s.p))
	if data.has("ramp"):
		var ramp := JumpRamp.new()
		var fr := frame_at(float(data.ramp.s) + 1.6)
		ramp.width = fr.w
		gp.add_child(ramp)
		ramp.global_transform = transform_at(float(data.ramp.s) + 1.6, 0.0, 0.8)
	var lights := Node3D.new()
	lights.name = "TunnelLights"
	gp.add_child(lights)
	for l in data.get("tunnel_lights", []):
		var o := OmniLight3D.new()
		o.light_color = Color(1.0, 0.72, 0.38)
		o.light_energy = 2.2
		o.omni_range = 11.0
		o.shadow_enabled = false
		lights.add_child(o)
		o.global_position = _v(l.p)
		var bulb := MeshInstance3D.new()
		var sphere := SphereMesh.new()
		sphere.radius = 0.25
		sphere.height = 0.5
		bulb.mesh = sphere
		bulb.material_override = Mats.std(Color(1, 0.8, 0.5), 0.3, 0.0, {"emit": Color(1.0, 0.7, 0.35), "emit_energy": 4.0})
		o.add_child(bulb)
	if data.has("waterfall_base"):
		var mist := Fx.make_particles({"amount": 40, "lifetime": 2.5, "dir": Vector3.UP, "spread": 60.0, "vmin": 1.0,
			"vmax": 3.0, "gravity": Vector3(0, 0.3, 0), "damp": 0.5, "tex": Fx.tex_puff, "blend": "mix",
			"size": Vector2(3.5, 3.5), "radius": 4.0, "scale_curve": [[0.0, 0.5], [1.0, 1.4]],
			"ramp": [[0.0, Color(1, 1, 1, 0.0)], [0.2, Color(1, 1, 1, 0.35)], [1.0, Color(1, 1, 1, 0.0)]]})
		gp.add_child(mist)
		mist.global_position = _v(data.waterfall_base)
		mist.emitting = true


# ---------------------------------------------------------------- decor

func _spawn_decor() -> void:
	var groups := {}
	for d in data.decor:
		groups.get_or_add(d.prop + ("@flip" if d.get("flip", false) else ""), []).append(d)
	var root := Node3D.new()
	root.name = "Decor"
	add_child(root)
	for key in groups:
		var prop: String = key.split("@")[0]
		var mirror: bool = key.ends_with("@flip")
		var path := "res://assets/models/props/%s.glb" % prop
		if not ResourceLoader.exists(path):
			continue
		var xforms: Array[Transform3D] = []
		for d in groups[key]:
			var s: float = d.s
			if prop == "start_arch":
				s *= 1.45
			var b := Basis(Vector3.UP, deg_to_rad(float(d.yaw))).scaled(Vector3.ONE * s)
			xforms.append(Transform3D(b, _v(d.p)))
		_multimesh(root, path, xforms, prop in ["start_arch", "grandstand", "rock_arch", "cliff_a", "cliff_b", "beach_hut"], 0.0, mirror)
	# crowds on every grandstand
	if groups.has("grandstand") and ResourceLoader.exists("res://assets/models/props/crowd_member.glb"):
		var crowd: Array[Transform3D] = []
		for d in groups["grandstand"]:
			var gb := Basis(Vector3.UP, deg_to_rad(float(d.yaw))).scaled(Vector3.ONE * float(d.s))
			var gt := Transform3D(gb, _v(d.p))
			for row in 6:
				var x := -6.7
				while x <= 6.7:
					if randf() < 0.78:
						var local := Transform3D(Basis(Vector3.UP, PI + randf_range(-0.3, 0.3)).scaled(Vector3.ONE * randf_range(0.8, 1.0)),
							Vector3(x + randf_range(-0.08, 0.08), 0.78 + 0.45 * row, 0.8 * row + 0.5))
						crowd.append(gt * local)
					x += 0.54
		_multimesh(root, "res://assets/models/props/crowd_member.glb", crowd, false, 260.0)
	var sc: Dictionary = data.get("scatter", {})
	for prop in sc:
		var path := "res://assets/models/props/%s.glb" % prop
		if not ResourceLoader.exists(path):
			continue
		var xf: Array[Transform3D] = []
		for e in sc[prop]:
			var b := Basis(Vector3.UP, e[3]).scaled(Vector3.ONE * e[4])
			xf.append(Transform3D(b, Vector3(e[0], e[1], e[2])))
		_multimesh(root, path, xf, false, 180.0)


func _multimesh(root: Node3D, path: String, xforms: Array[Transform3D], shadows: bool, vis_range := 0.0, mirror := false) -> void:
	var ps := load(path) as PackedScene
	var inst := ps.instantiate()
	Mats.apply(inst, "world")
	for node in inst.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		var mesh := (_mirrored(mi.mesh) if mirror else mi.mesh.duplicate()) as Mesh
		for i in mesh.get_surface_count():
			var ov := mi.get_surface_override_material(i)
			if ov:
				mesh.surface_set_material(i, ov)
		var local := _relative_xform(inst, mi)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_custom_data = true
		mm.mesh = mesh
		mm.instance_count = xforms.size()
		for k in xforms.size():
			mm.set_instance_transform(k, xforms[k] * local)
			mm.set_instance_custom_data(k, Color.from_hsv(randf(), randf_range(0.35, 0.7), 1.0, randf()))
		var mmi := MultiMeshInstance3D.new()
		mmi.multimesh = mm
		mmi.name = path.get_file().get_basename() + "_" + mi.name
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows or vis_range == 0.0 else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		if vis_range > 0.0:
			mmi.visibility_range_end = vis_range
			mmi.visibility_range_end_margin = 20.0
			mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		root.add_child(mmi)
	inst.free()


## X-mirrored copy with flipped winding (so culling stays correct).
func _mirrored(src: Mesh) -> ArrayMesh:
	var out := ArrayMesh.new()
	for i in src.get_surface_count():
		var arr := src.surface_get_arrays(i)
		var v: PackedVector3Array = arr[Mesh.ARRAY_VERTEX]
		for k in v.size():
			v[k].x = -v[k].x
		arr[Mesh.ARRAY_VERTEX] = v
		if arr[Mesh.ARRAY_NORMAL] != null:
			var nn: PackedVector3Array = arr[Mesh.ARRAY_NORMAL]
			for k in nn.size():
				nn[k].x = -nn[k].x
			arr[Mesh.ARRAY_NORMAL] = nn
		arr[Mesh.ARRAY_TANGENT] = null
		if arr[Mesh.ARRAY_INDEX] != null:
			var idx: PackedInt32Array = arr[Mesh.ARRAY_INDEX]
			for k in range(0, idx.size(), 3):
				var t := idx[k + 1]
				idx[k + 1] = idx[k + 2]
				idx[k + 2] = t
			arr[Mesh.ARRAY_INDEX] = idx
		out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
		out.surface_set_material(i, src.surface_get_material(i))
	return out


func _relative_xform(root: Node, node: Node3D) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = node
	while cur != null and cur != root:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t


# ---------------------------------------------------------------- queries

func index_of_s(s: float) -> int:
	return posmod(int(round(s / step)), n)


func nearest_index(p: Vector3, hint := -1, window := 40) -> int:
	var best := 0
	var bd := INF
	if hint < 0:
		for i in range(0, n, 2):
			var d := p.distance_squared_to(pos[i])
			if d < bd:
				bd = d
				best = i
		hint = best
	bd = INF
	for k in range(-window, window + 1):
		var i := posmod(hint + k, n)
		var d := p.distance_squared_to(pos[i])
		if d < bd:
			bd = d
			best = i
	return best


## {index, s (refined), lateral, dist}
func locate(p: Vector3, hint := -1) -> Dictionary:
	var i := nearest_index(p, hint)
	var rel := p - pos[i]
	var along := rel.dot(fwd[i])
	var lat := rel.dot(right[i])
	var s := fposmod(svals[i] + along, length)
	return {"index": i, "s": s, "lateral": lat, "height": rel.dot(upv[i]), "half_width": width[i] * 0.5}


func frame_at(s: float) -> Dictionary:
	var f := fposmod(s, length) / step
	var i0 := int(floorf(f)) % n
	var i1 := (i0 + 1) % n
	var t := f - floorf(f)
	return {"p": pos[i0].lerp(pos[i1], t), "f": fwd[i0].slerp(fwd[i1], t).normalized(),
		"r": right[i0].slerp(right[i1], t).normalized(), "u": upv[i0].slerp(upv[i1], t).normalized(),
		"w": lerpf(width[i0], width[i1], t), "c": lerpf(curv[i0], curv[i1], t), "i": i0}


func transform_at(s: float, lateral := 0.0, lift := 0.5) -> Transform3D:
	var fr := frame_at(s)
	var b := Basis(fr.r, fr.u, -fr.f).orthonormalized()
	return Transform3D(b, fr.p + fr.r * lateral + fr.u * lift)


## Mean signed curvature over the next `dist` metres (+ = left turn).
func curvature_ahead(s: float, dist: float, from := 0.0) -> float:
	var acc := 0.0
	var cnt := 0
	var d := from
	while d <= dist:
		acc += curv[index_of_s(s + d)]
		cnt += 1
		d += step
	return acc / maxf(cnt, 1)


func has_tag(s: float, tag: String) -> bool:
	return tag in tags[index_of_s(s)]


func grid_transform(slot: int) -> Transform3D:
	var g: Dictionary = data.grid[slot % data.grid.size()]
	return Transform3D(_basis(g), _v(g.p))
