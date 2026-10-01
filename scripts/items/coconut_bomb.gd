class_name CoconutBomb
extends Node3D
## Thrown coconut bomb: rolls down the track following its direction, bounces,
## sizzles, and explodes on contact or when the fuse runs out.

const RADIUS := 5.5
var owner_kart: Kart
var track: Track
var velocity := Vector3.ZERO
var fuse := 3.2
var hint := -1
var visual: Node3D
var _spin := 0.0
var _fuse_snd: AudioStreamPlayer3D


func _ready() -> void:
	var path := "res://assets/models/props/coconut_bomb.glb"
	if ResourceLoader.exists(path):
		visual = (load(path) as PackedScene).instantiate()
		Mats.apply(visual, "world")
	else:
		var mi := MeshInstance3D.new()
		var sm := SphereMesh.new()
		sm.radius = 0.4
		sm.height = 0.8
		mi.mesh = sm
		mi.material_override = Mats.std(Color("6b4226"), 0.8)
		visual = mi
	add_child(visual)
	visual.position.y = -0.3
	var spark := Fx.make_particles({"amount": 20, "lifetime": 0.3, "dir": Vector3.UP, "spread": 60.0, "vmin": 1.0,
		"vmax": 3.0, "gravity": Vector3(0, -3, 0), "tex": Fx.tex_star, "size": Vector2(0.18, 0.18),
		"ramp": [[0.0, Color(1, 1, 0.6, 1)], [1.0, Color(1, 0.4, 0.1, 0)]]})
	spark.position = Vector3(0, 0.55, 0)
	add_child(spark)
	spark.emitting = true
	_fuse_snd = Audio.make_loop("bomb_fuse", self, -2.0)


func _physics_process(dt: float) -> void:
	fuse -= dt
	if track:
		var loc := track.locate(global_position, hint)
		hint = loc.index
		var fr := track.frame_at(loc.s + 6.0)
		var want: Vector3 = (fr.p + fr.r * clampf(loc.lateral, -3.0, 3.0) * 0.5) - global_position
		want.y = 0.0
		var hv := Vector3(velocity.x, 0, velocity.z)
		var sp := hv.length()
		hv = hv.slerp(want.normalized() * sp, 1.0 - exp(-dt * 2.5))
		velocity.x = hv.x
		velocity.z = hv.z
	velocity.y -= 30.0 * dt
	var space := get_world_3d().direct_space_state
	var next := global_position + velocity * dt
	var q := PhysicsRayQueryParameters3D.create(global_position + Vector3.UP * 0.8, next + Vector3.DOWN * 0.45, 1)
	var r := space.intersect_ray(q)
	if not r.is_empty():
		next.y = r.position.y + 0.42
		if velocity.y < -4.0:
			velocity.y = -velocity.y * 0.45
			Audio.play_at("land", global_position, -6.0, 1.6)
		else:
			velocity.y = maxf(velocity.y, 0.0)
	global_position = next
	_spin += velocity.length() * dt * 2.0
	visual.rotation.x = -_spin
	for k in get_tree().get_nodes_in_group("karts"):
		var kk := k as Kart
		if kk == owner_kart and fuse > 2.9:
			continue
		if kk.global_position.distance_to(global_position) < 1.6:
			explode()
			return
	if fuse <= 0.0 or global_position.y < -20.0:
		explode()


func explode() -> void:
	Fx.burst("explosion", global_position, Vector3.UP, Color.WHITE, 1.0)
	Audio.play_at("explosion", global_position, 3.0)
	Juice.shake(0.35)
	for k in get_tree().get_nodes_in_group("karts"):
		var kk := k as Kart
		var d := kk.global_position.distance_to(global_position)
		if d < RADIUS:
			if kk.spin_out("bomb", 1.5):
				kk.vertical = 8.0
				kk.grounded = false
			if kk.is_player:
				Juice.shake(0.6)
				Juice.rumble(1.0, 1.0, 0.4)
	queue_free()
