class_name KartModel
extends Node3D
## Visual kart assembled from a KartConfig (see KartParts). Hierarchy:
##   KartModel            <- Kart rotates this for drift angle / spin-outs
##     Body               <- sprung: roll, pitch, bounce, squash & stretch
##       chassis, body, wing, engine parts; DriverMount
##     Wheels
##       FL/FR/RL/RR -> Steer -> Spin -> mesh
## Everything is rebuilt from data, so the garage can hot-swap parts.

signal rebuilt

const REF_FRONT_R := 0.20
const REF_REAR_R := 0.24
const STEER_AXIS := Vector3(0.0, -0.555, -0.832)

var config: KartConfig
var body: Node3D
var wheels_root: Node3D
var driver_mount: Node3D
var steering_wheel: Node3D
var exhausts: Array[Node3D] = []
var wheels := {}          # "fl" -> {"pivot", "steer", "spin", "radius", "left"}
var front_radius := REF_FRONT_R
var rear_radius := REF_REAR_R
var lift := 0.0

var paint_mat: ShaderMaterial
var alt_mat: StandardMaterial3D
var rim_mat: StandardMaterial3D

var _parts := {}          # slot -> Node3D instance
var _sw_rest: Transform3D
var _spin_angle := 0.0
var _chassis: Node3D


func _init(cfg: KartConfig = null) -> void:
	config = cfg if cfg else KartConfig.new()


func _ready() -> void:
	if body == null:
		build(config)


func build(cfg: KartConfig) -> void:
	config = cfg
	for c in get_children():
		c.free()
	_parts.clear()
	wheels.clear()
	exhausts.clear()
	paint_mat = Mats.kart_paint(cfg.color_primary, cfg.color_secondary, cfg.pattern)
	alt_mat = Mats.std(cfg.color_secondary, 0.3, 0.05, {"coat": 0.7})
	rim_mat = Mats.std(cfg.color_rim, 0.26, 0.35)
	body = Node3D.new()
	body.name = "Body"
	add_child(body)
	wheels_root = Node3D.new()
	wheels_root.name = "Wheels"
	add_child(wheels_root)
	_chassis = _instance(KartParts.CHASSIS)
	body.add_child(_chassis)
	driver_mount = Node3D.new()
	driver_mount.name = "DriverMount"
	body.add_child(driver_mount)
	var sock := _chassis.find_child("socket_driver", true, false) as Node3D
	if sock:
		driver_mount.position = sock.position
	steering_wheel = _chassis.find_child("SteeringWheel", true, false) as Node3D
	if steering_wheel:
		_sw_rest = steering_wheel.transform
	for slot in ["body", "wing", "engine"]:
		_build_slot(slot)
	_build_wheels()
	_apply_lift()
	rebuilt.emit()


func _instance(path: String) -> Node3D:
	var ps := load(path) as PackedScene
	var n: Node3D = ps.instantiate() if ps else Node3D.new()
	Mats.apply(n, "kart", {"Paint": paint_mat, "PaintAlt": alt_mat, "Rim": rim_mat})
	for mi in n.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	return n


func _build_slot(slot: String) -> void:
	if _parts.has(slot):
		_parts[slot].queue_free()
	var info := KartParts.part(slot, config.get(slot))
	var inst := _instance(info.scene)
	inst.name = slot.capitalize()
	body.add_child(inst)
	_parts[slot] = inst
	if slot == "engine":
		exhausts.clear()
		for n in inst.find_children("socket_exhaust_*", "", true, false):
			exhausts.append(n as Node3D)


func _build_wheels() -> void:
	for c in wheels_root.get_children():
		c.free()
	wheels.clear()
	var info := KartParts.part("wheels", config.wheels)
	front_radius = info.get("front_r", REF_FRONT_R)
	rear_radius = info.get("rear_r", REF_REAR_R)
	var src := _instance(info.scene)
	var meshes := {}
	for mi in src.find_children("*", "MeshInstance3D", true, false):
		meshes[mi.name] = mi
	for key in ["fl", "fr", "rl", "rr"]:
		var sock := _chassis.find_child("socket_wheel_" + key, true, false) as Node3D
		var front: bool = key.begins_with("f")
		var left: bool = key.ends_with("l")
		var r := front_radius if front else rear_radius
		var pivot := Node3D.new()
		pivot.name = "Wheel_" + key.to_upper()
		pivot.position = Vector3(sock.position.x if sock else (0.57 if not left else -0.57), r, sock.position.z if sock else 0.0)
		wheels_root.add_child(pivot)
		var steer := Node3D.new()
		pivot.add_child(steer)
		var spin := Node3D.new()
		steer.add_child(spin)
		var orig: MeshInstance3D = meshes.get("wheel_front" if front else "wheel_rear")
		if orig:
			var mi := MeshInstance3D.new()
			mi.mesh = orig.mesh
			for i in orig.mesh.get_surface_count():
				mi.set_surface_override_material(i, orig.get_surface_override_material(i))
			spin.add_child(mi)
			if left:
				mi.rotation.y = PI
		wheels[key] = {"pivot": pivot, "steer": steer, "spin": spin, "radius": r, "left": left, "front": front,
			"rest_y": r}
	src.free()


func _apply_lift() -> void:
	lift = rear_radius - REF_REAR_R
	body.position.y = lift


## Garage hot-swap with a squash-and-stretch pop.
func swap_part(slot: String, id: String) -> void:
	config.set(slot, id)
	if slot == "wheels":
		_build_wheels()
		_apply_lift()
		_pop(wheels_root)
	else:
		_build_slot(slot)
		_pop(_parts[slot])
	rebuilt.emit()


func refresh_paint() -> void:
	paint_mat.set_shader_parameter("primary", config.color_primary)
	paint_mat.set_shader_parameter("secondary", config.color_secondary)
	paint_mat.set_shader_parameter("pattern", config.pattern)
	alt_mat.albedo_color = config.color_secondary
	rim_mat.albedo_color = config.color_rim


func _pop(n: Node3D) -> void:
	n.scale = Vector3(0.6, 1.35, 0.6)
	var tw := create_tween()
	tw.tween_property(n, "scale", Vector3(1.15, 0.88, 1.15), 0.09).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(n, "scale", Vector3.ONE, 0.35).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)


# ---------------------------------------------------------------- animation API

## Roll/pitch in radians, bounce in metres, squash = (xz, y) scale factors.
func set_body_pose(roll: float, pitch: float, bounce: float, squash: Vector2, jitter := Vector3.ZERO) -> void:
	body.position = Vector3(jitter.x, lift + bounce + jitter.y, jitter.z)
	body.rotation = Vector3(pitch, 0.0, roll)
	body.scale = Vector3(squash.x, squash.y, squash.x)


func set_steer(angle: float, wheel_angle: float) -> void:
	for key in ["fl", "fr"]:
		if wheels.has(key):
			wheels[key].steer.rotation.y = angle
	if steering_wheel:
		steering_wheel.transform = _sw_rest * Transform3D(Basis(STEER_AXIS.normalized(), wheel_angle), Vector3.ZERO)


## Advance wheel spin by distance travelled (m); per-wheel suspension offsets.
func roll_wheels(distance: float, susp := {}) -> void:
	for key in wheels:
		var w: Dictionary = wheels[key]
		var ang: float = -distance / float(w.radius)
		(w.spin as Node3D).rotate_x(ang)
		if susp.has(key):
			(w.pivot as Node3D).position.y = float(w.rest_y) + float(susp[key])


func wheel_contact(key: String) -> Vector3:
	var w: Dictionary = wheels.get(key, {})
	if w.is_empty():
		return global_position
	var p: Node3D = w.pivot
	return p.global_position - global_transform.basis.y * float(w.radius) * 0.95


func set_flash(amount: float, color := Color.WHITE) -> void:
	paint_mat.set_shader_parameter("flash", amount)
	paint_mat.set_shader_parameter("flash_color", color)


func set_ghost(amount: float) -> void:
	paint_mat.set_shader_parameter("ghost", amount)
