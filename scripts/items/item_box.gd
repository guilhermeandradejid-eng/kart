class_name ItemBox
extends Area3D
## Floating rainbow "?" box. Shatters into confetti, hands out an item via the
## race's weighted roulette and pops back with an elastic scale-in.

const RESPAWN := 2.2
var visual: Node3D
var active := true
var _t := randf() * 10.0
var _base_y := 0.0


func _ready() -> void:
	collision_layer = 4
	collision_mask = 2
	monitorable = false
	var cs := CollisionShape3D.new()
	var sp := SphereShape3D.new()
	sp.radius = 1.25
	cs.shape = sp
	add_child(cs)
	var path := "res://assets/models/props/item_box.glb"
	if ResourceLoader.exists(path):
		visual = (load(path) as PackedScene).instantiate()
		Mats.apply(visual, "world")
	else:
		visual = MeshInstance3D.new()
		var bm := BoxMesh.new()
		bm.size = Vector3.ONE * 1.1
		(visual as MeshInstance3D).mesh = bm
		(visual as MeshInstance3D).material_override = Mats.get_mat("world", "ItemBox")
	add_child(visual)
	_base_y = visual.position.y
	body_entered.connect(_on_body)


func _process(dt: float) -> void:
	_t += dt
	if visual:
		visual.rotation = Vector3(sin(_t * 0.9) * 0.25, _t * 1.4, cos(_t * 0.7) * 0.2)
		visual.position.y = _base_y + sin(_t * 2.2) * 0.12


func _on_body(b: Node) -> void:
	if not active or not (b is Kart):
		return
	var k := b as Kart
	active = false
	Fx.burst("shatter", global_position, Vector3.UP, Color.WHITE, 1.0)
	visual.visible = false
	if k.is_player:
		Audio.play("item_box", -1.0, randf_range(0.95, 1.05))
		Juice.rumble(0.3, 0.1, 0.1)
	else:
		Audio.play_at("item_box", global_position, -6.0)
	if k.item == "" and k.race:
		k.give_item(k.race.roll_item(k))
	get_tree().create_timer(RESPAWN).timeout.connect(_respawn)


func _respawn() -> void:
	active = true
	visual.visible = true
	visual.scale = Vector3.ONE * 0.05
	create_tween().tween_property(visual, "scale", Vector3.ONE, 0.55).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
