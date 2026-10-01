class_name Showroom
extends Node3D
## Shared 3D stage for menus and the garage: sunset-lit beach podium, palms,
## the player's kart on a turntable with Guará in it, and a slow orbit camera.

var kart_model: KartModel
var driver: Driver
var turntable: Node3D
var camera: Camera3D
var orbit_speed := 0.12
var cam_target := Vector3(0, 0.7, 0)
var cam_dist := 4.6
var cam_height := 1.5
var cam_yaw := 0.6
var spin := true
var garage := false
var _t := 0.0


func _ready() -> void:
	var we := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_SKY
	var sky := Sky.new()
	var sm := ShaderMaterial.new()
	sm.shader = load("res://shaders/track/sky.gdshader")
	sm.set_shader_parameter("noise_tex", Mats.noise())
	if not garage:
		sm.set_shader_parameter("zenith", Color(0.22, 0.32, 0.72))
		sm.set_shader_parameter("horizon", Color(1.0, 0.68, 0.45))
		sm.set_shader_parameter("sun_color", Color(1.0, 0.75, 0.45))
	sky.sky_material = sm
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_AGX
	e.glow_enabled = true
	e.glow_intensity = 0.6
	e.glow_hdr_threshold = 1.0
	e.ssao_enabled = true
	e.adjustment_enabled = true
	e.adjustment_saturation = 1.12
	if garage:
		e.background_mode = Environment.BG_COLOR
		e.background_color = Color(0.06, 0.07, 0.13)
		e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
		e.ambient_light_color = Color(0.35, 0.4, 0.6)
		e.ambient_light_energy = 0.6
	we.environment = e
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.light_color = Color(1.0, 0.82, 0.62) if not garage else Color(1, 0.96, 0.9)
	sun.light_energy = 1.4
	sun.rotation_degrees = Vector3(-28 if not garage else -55, 35, 0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 30.0
	add_child(sun)
	if garage:
		for side in [-1, 1]:
			var spot := SpotLight3D.new()
			spot.light_color = Color(0.55, 0.8, 1.0) if side < 0 else Color(1.0, 0.6, 0.35)
			spot.light_energy = 18.0
			spot.spot_range = 12.0
			spot.spot_angle = 35.0
			spot.position = Vector3(side * 3.5, 4.0, 2.0)
			add_child(spot)
			spot.look_at(Vector3(0, 0.5, 0))
	# podium
	var podium := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = 2.4
	cyl.bottom_radius = 2.55
	cyl.height = 0.3
	cyl.radial_segments = 64
	podium.mesh = cyl
	podium.position.y = -0.15
	podium.material_override = Mats.std(Color("2b2f4a") if garage else Color("f2d49a"), 0.6, 0.0, {"rim": 0.2})
	add_child(podium)
	var ring := MeshInstance3D.new()
	var tor := TorusMesh.new()
	tor.inner_radius = 2.42
	tor.outer_radius = 2.56
	ring.mesh = tor
	ring.material_override = Mats.std(Color("ffd23f"), 0.3, 0.0, {"emit": Color("ffb020"), "emit_energy": 2.0})
	add_child(ring)
	var ground := MeshInstance3D.new()
	var pm := PlaneMesh.new()
	pm.size = Vector2(80, 80)
	ground.mesh = pm
	ground.position.y = -0.3
	ground.material_override = Mats.std(Color("1a1d33") if garage else Color("e8c98d"), 0.9)
	add_child(ground)
	if not garage:
		var sea := MeshInstance3D.new()
		var sp := PlaneMesh.new()
		sp.size = Vector2(400, 200)
		sea.mesh = sp
		sea.position = Vector3(0, -0.28, -120)
		sea.material_override = Mats.std(Color("2bb3c9"), 0.08, 0.0, {"emit": Color("1a6f8a"), "emit_energy": 0.3})
		add_child(sea)
		for p in [[Vector3(-4.5, -0.3, -3.0), 1.1, "palm_a"], [Vector3(5.0, -0.3, -4.5), 1.3, "palm_b"],
				[Vector3(-7.5, -0.3, -9.0), 1.0, "palm_c"], [Vector3(3.0, -0.3, -12.0), 1.2, "palm_a"],
				[Vector3(-3.0, -0.3, 3.5), 0.9, "bush_a"], [Vector3(3.8, -0.3, 2.5), 0.7, "flowers"],
				[Vector3(6.5, -0.3, 1.0), 1.0, "umbrella"], [Vector3(-6.0, -0.3, 0.5), 1.0, "beach_chair"]]:
			var path := "res://assets/models/props/%s.glb" % p[2]
			if ResourceLoader.exists(path):
				var n: Node3D = (load(path) as PackedScene).instantiate()
				Mats.apply(n, "world")
				n.position = p[0]
				n.scale = Vector3.ONE * p[1]
				n.rotation.y = randf() * TAU
				add_child(n)
	turntable = Node3D.new()
	add_child(turntable)
	kart_model = KartModel.new(Game.player_config)
	turntable.add_child(kart_model)
	kart_model.build(Game.player_config)
	driver = Driver.new(Game.player_config.driver_variant)
	kart_model.driver_mount.add_child(driver)
	camera = Camera3D.new()
	camera.fov = 45.0
	add_child(camera)
	camera.current = true
	_update_camera(0.0)


func set_driver_state(s: String) -> void:
	if driver and driver.tree:
		driver.set_state(s)


func rebuild() -> void:
	kart_model.build(Game.player_config)
	driver = Driver.new(Game.player_config.driver_variant)
	kart_model.driver_mount.add_child(driver)


func _process(dt: float) -> void:
	_t += dt
	if spin:
		turntable.rotation.y += dt * 0.35
	_update_camera(dt)
	if driver and driver.tree and _t > 0.2 and driver._state == "race":
		driver.set_state("wave")


func _update_camera(dt: float) -> void:
	cam_yaw += dt * orbit_speed * 0.0
	var off := Vector3(sin(cam_yaw), 0, cos(cam_yaw)) * cam_dist + Vector3.UP * cam_height
	camera.position = camera.position.lerp(cam_target + off, 1.0 - exp(-maxf(dt, 0.0001) * 4.0)) if dt > 0.0 else cam_target + off
	camera.look_at(cam_target, Vector3.UP)
