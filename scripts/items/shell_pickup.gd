class_name ShellPickup
extends Area3D
## Golden seashell (the track's "coin"): each one adds a little top speed.

var visual: Node3D
var _t := randf() * 6.0
var active := true


func _ready() -> void:
	collision_layer = 4
	collision_mask = 2
	monitorable = false
	var cs := CollisionShape3D.new()
	var sp := SphereShape3D.new()
	sp.radius = 1.0
	cs.shape = sp
	add_child(cs)
	var path := "res://assets/models/props/seashell.glb"
	if ResourceLoader.exists(path):
		visual = (load(path) as PackedScene).instantiate()
		Mats.apply(visual, "world")
	else:
		var mi := MeshInstance3D.new()
		var tm := TorusMesh.new()
		tm.inner_radius = 0.15
		tm.outer_radius = 0.35
		mi.mesh = tm
		mi.material_override = Mats.get_mat("world", "Gold")
		visual = mi
	add_child(visual)
	body_entered.connect(_on_body)


func _process(dt: float) -> void:
	_t += dt
	if visual and visual.visible:
		visual.rotation.y = _t * 2.6
		visual.position.y = sin(_t * 3.0) * 0.1


func _on_body(b: Node) -> void:
	if not active or not (b is Kart):
		return
	var k := b as Kart
	if k.shells >= Kart.MAX_SHELLS and not k.is_player:
		return
	active = false
	k.add_shells(1)
	Fx.burst("pickup", global_position, Vector3.UP, Color(1, 0.85, 0.3), 1.0)
	if k.is_player:
		Audio.play("coin", -2.0, 1.0 + 0.04 * k.shells)
		Fx.float_text("+1", global_position + Vector3.UP * 0.6, Color("ffd23f"))
	visual.visible = false
	get_tree().create_timer(9.0).timeout.connect(func():
		active = true
		visual.visible = true
		visual.scale = Vector3.ONE * 0.1
		create_tween().tween_property(visual, "scale", Vector3.ONE, 0.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT))
