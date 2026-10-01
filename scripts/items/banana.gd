class_name Banana
extends Area3D
## Banana peel trap. Spins out whoever drives over it (owner is immune briefly).

var owner_kart: Kart
var _grace := 0.5
var visual: Node3D
var _wobble := 0.0


func _ready() -> void:
	collision_layer = 8
	collision_mask = 2
	var cs := CollisionShape3D.new()
	var sp := SphereShape3D.new()
	sp.radius = 0.8
	cs.shape = sp
	cs.position.y = 0.3
	add_child(cs)
	var path := "res://assets/models/props/banana_peel.glb"
	if ResourceLoader.exists(path):
		visual = (load(path) as PackedScene).instantiate()
		Mats.apply(visual, "world")
	else:
		var mi := MeshInstance3D.new()
		var cm := CapsuleMesh.new()
		cm.radius = 0.18
		cm.height = 0.7
		mi.mesh = cm
		mi.rotation.z = PI / 2
		mi.material_override = Mats.std(Color("ffd83a"), 0.5)
		visual = mi
	add_child(visual)
	visual.scale = Vector3(1.4, 0.4, 1.4)
	create_tween().tween_property(visual, "scale", Vector3.ONE, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	body_entered.connect(_on_body)
	add_to_group("hazards")


func _process(dt: float) -> void:
	_grace -= dt
	_wobble += dt
	visual.rotation.y = sin(_wobble * 1.3) * 0.2


func _on_body(b: Node) -> void:
	if not (b is Kart):
		return
	var k := b as Kart
	if k == owner_kart and _grace > 0.0:
		return
	if k.spin_out("banana"):
		Audio.play_at("banana_slip", global_position, 0.0)
		Fx.burst("poof", global_position + Vector3.UP * 0.3, Vector3.UP, Color.WHITE, 0.6)
		queue_free()
