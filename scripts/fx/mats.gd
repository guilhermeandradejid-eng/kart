class_name Mats
extends RefCounted
## Art-direction hub: every imported .glb surface is re-materialised here by the
## material NAME it was given in Blender (see tools/blender/tt/core.py). Three
## sets: "kart" (hard-surface), "character" (fur/cloth/eyes) and "world"
## (track + props, vertex coloured). Materials are cached and shared.

static var _cache := {}
static var _noise: NoiseTexture2D
static var _normal: NoiseTexture2D


static func noise() -> NoiseTexture2D:
	if _noise == null:
		_noise = NoiseTexture2D.new()
		_noise.width = 512
		_noise.height = 512
		_noise.seamless = true
		_noise.generate_mipmaps = true
		var fn := FastNoiseLite.new()
		fn.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		fn.frequency = 0.008
		fn.fractal_octaves = 4
		_noise.noise = fn
	return _noise


static func normal_noise() -> NoiseTexture2D:
	if _normal == null:
		_normal = NoiseTexture2D.new()
		_normal.width = 512
		_normal.height = 512
		_normal.seamless = true
		_normal.as_normal_map = true
		_normal.bump_strength = 8.0
		_normal.generate_mipmaps = true
		var fn := FastNoiseLite.new()
		fn.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		fn.frequency = 0.02
		fn.fractal_octaves = 3
		_normal.noise = fn
	return _normal


static func base_name(m: Material) -> String:
	var n := m.resource_name
	var dot := n.find(".")
	if dot > 0:
		n = n.substr(0, dot)
	return n


static func std(color: Color, rough := 0.6, metal := 0.0, opts := {}) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = rough
	m.metallic = metal
	m.diffuse_mode = BaseMaterial3D.DIFFUSE_BURLEY
	if opts.get("vcol", false):
		m.vertex_color_use_as_albedo = true
	if opts.has("rim"):
		m.rim_enabled = true
		m.rim = opts.rim
		m.rim_tint = 0.5
	if opts.has("coat"):
		m.clearcoat_enabled = true
		m.clearcoat = opts.coat
		m.clearcoat_roughness = 0.1
	if opts.has("emit"):
		m.emission_enabled = true
		m.emission = opts.emit
		m.emission_energy_multiplier = opts.get("emit_energy", 1.0)
	if opts.has("alpha"):
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.albedo_color.a = opts.alpha
	if opts.get("unshaded", false):
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	return m


static func shader_mat(path: String, params := {}) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load(path)
	for k in params:
		m.set_shader_parameter(k, params[k])
	return m


static func stylized(params := {}) -> ShaderMaterial:
	return shader_mat("res://shaders/stylized.gdshader", params)


static func get_mat(set_name: String, n: String) -> Material:
	var key := set_name + ":" + n
	if _cache.has(key):
		return _cache[key]
	var m: Material = _build(set_name, n)
	_cache[key] = m
	return m


static func _build(set_name: String, n: String) -> Material:
	match set_name:
		"kart":
			match n:
				"Tire": return std(Color("33333b"), 0.9, 0.0, {"rim": 0.25})
				"Chrome": return std(Color("e3e7ec"), 0.12, 1.0)
				"Metal": return std(Color("a1a7b1"), 0.32, 0.85)
				"Plastic": return std(Color("2b2c33"), 0.5, 0.0, {"rim": 0.15})
				"Seat": return std(Color("30313a"), 0.78, 0.0, {"rim": 0.2})
				"Light": return std(Color("fff4c8"), 0.2, 0.0, {"emit": Color("fff0b0"), "emit_energy": 3.0})
				"Decal": return std(Color("f4f4f0"), 0.4)
				"Glass": return std(Color(0.7, 0.9, 1.0), 0.05, 0.2, {"alpha": 0.4})
				"PaintAlt": return std(Color("ffc93c"), 0.3, 0.05, {"coat": 0.7})
				"Rim": return std(Color("ffd23f"), 0.28, 0.35)
				"Paint": return kart_paint(Color("e0342c"), Color("ffc93c"), 1)
		"character":
			match n:
				"Fur": return shader_mat("res://shaders/fur.gdshader")
				"Cloth": return shader_mat("res://shaders/fur.gdshader", {"sheen": 0.15, "roughness_v": 0.9, "translucency": 0.05})
				"Scarf": return shader_mat("res://shaders/fur.gdshader", {"sheen": 0.3, "roughness_v": 0.9, "translucency": 0.3})
				"Nose": return std(Color("1b1616"), 0.12, 0.0, {"coat": 1.0})
				"EyeWhite": return std(Color("fbfaf6"), 0.08, 0.0, {"coat": 1.0})
				"Iris": return std(Color("e89a2c"), 0.15, 0.0, {"emit": Color("f0a030"), "emit_energy": 0.25, "coat": 1.0})
				"Pupil": return std(Color("0e0908"), 0.05, 0.0, {"coat": 1.0})
				"Glint": return std(Color.WHITE, 1.0, 0.0, {"unshaded": true})
				"Mouth": return std(Color("561a20"), 0.6)
				"Tongue": return std(Color("ea6f7b"), 0.35, 0.0, {"coat": 0.6})
				"Teeth": return std(Color("fbf7ee"), 0.3)
				"Lens": return std(Color("7ad8ff"), 0.04, 0.4, {"coat": 1.0, "rim": 0.4})
				"Brass": return std(Color("d19a3e"), 0.28, 0.95)
				"Strap": return std(Color("6b3d24"), 0.72, 0.0, {"rim": 0.15})
		"world":
			match n:
				"Road": return shader_mat("res://shaders/track/road.gdshader", {"noise_tex": noise()})
				"Planks": return shader_mat("res://shaders/track/planks.gdshader", {"noise_tex": noise()})
				"Terrain": return shader_mat("res://shaders/track/terrain.gdshader", {"noise_tex": noise()})
				"Checker": return shader_mat("res://shaders/track/checker.gdshader")
				"Water": return shader_mat("res://shaders/track/water.gdshader", {"noise_tex": noise(), "normal_tex": normal_noise()})
				"Waterfall": return shader_mat("res://shaders/track/waterfall.gdshader", {"noise_tex": noise()})
				"TunnelRock": return stylized({"roughness_v": 0.95, "detail": 0.18, "detail_scale": 0.8})
				"Rock": return stylized({"roughness_v": 0.9, "detail": 0.14, "detail_scale": 0.9, "rim_v": 0.15})
				"Leaf": return stylized({"roughness_v": 0.6, "detail": 0.06, "wind": 0.35, "rim_v": 0.25})
				"Flower": return stylized({"roughness_v": 0.55, "detail": 0.04, "wind": 0.18, "rim_v": 0.3})
				"Bark": return stylized({"roughness_v": 0.9, "detail": 0.15, "detail_scale": 3.0, "wind": 0.05})
				"Wood": return stylized({"roughness_v": 0.8, "detail": 0.12, "detail_scale": 4.0})
				"Straw": return stylized({"roughness_v": 0.95, "detail": 0.2, "detail_scale": 6.0, "wind": 0.04})
				"Fabric": return stylized({"roughness_v": 0.85, "detail": 0.03, "wind": 0.25})
				"Rope": return stylized({"roughness_v": 0.95, "detail": 0.1, "detail_scale": 8.0})
				"Sand": return stylized({"roughness_v": 0.95, "detail": 0.08})
				"Plastic": return stylized({"roughness_v": 0.45, "detail": 0.0, "rim_v": 0.2})
				"Paint": return stylized({"roughness_v": 0.35, "detail": 0.0, "rim_v": 0.25})
				"Metal": return stylized({"roughness_v": 0.3, "metallic_v": 0.8, "detail": 0.0})
				"Tire": return stylized({"roughness_v": 0.9, "detail": 0.03})
				"Glass": return std(Color(0.75, 0.92, 1.0), 0.05, 0.1, {"alpha": 0.45, "vcol": true})
				"Emissive": return shader_mat("res://shaders/emissive_pulse.gdshader")
				"Gold": return shader_mat("res://shaders/gold.gdshader")
				"ItemBox": return shader_mat("res://shaders/item_box.gdshader")
				"BoostPad": return shader_mat("res://shaders/boost_pad.gdshader")
				"Crowd": return stylized({"roughness_v": 0.7, "detail": 0.0, "instance_tint": 1.0, "rim_v": 0.3, "bounce": 0.14})
	return null


static func kart_paint(primary: Color, secondary: Color, pattern: int) -> ShaderMaterial:
	return shader_mat("res://shaders/kart_paint.gdshader", {"primary": primary, "secondary": secondary, "pattern": pattern})


## Re-materialise every mesh under `root`. `overrides` maps material names to
## per-instance materials (kart paint, character colourways).
static func apply(root: Node, set_name: String, overrides := {}) -> void:
	for node in root.find_children("*", "MeshInstance3D", true, false):
		var mi := node as MeshInstance3D
		if mi.mesh == null:
			continue
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m == null:
				continue
			var n := base_name(m)
			var rep: Material = overrides.get(n, null)
			if rep == null:
				rep = get_mat(set_name, n)
			if rep != null:
				mi.set_surface_override_material(i, rep)
