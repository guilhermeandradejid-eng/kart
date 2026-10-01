class_name BoostPad
extends Area3D
## Dash panel: instant boost, pad flashes, the kart gets a flame burst.

var visual: Node3D
var _cool := {}


func _ready() -> void:
	collision_layer = 4
	collision_mask = 2
	monitorable = false
	var cs := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = Vector3(4.2, 1.6, 5.2)
	cs.shape = bx
	cs.position.y = 0.6
	add_child(cs)
	var path := "res://assets/models/props/boost_pad.glb"
	if ResourceLoader.exists(path):
		visual = (load(path) as PackedScene).instantiate()
		Mats.apply(visual, "world")
	else:
		var mi := MeshInstance3D.new()
		var pm := PlaneMesh.new()
		pm.size = Vector2(4.0, 5.0)
		mi.mesh = pm
		mi.material_override = Mats.get_mat("world", "BoostPad")
		mi.position.y = 0.04
		visual = mi
	# glTF pads are modelled with +Y (Blender) forward = -Z here; chevrons scroll forward
	add_child(visual)
	body_entered.connect(_on_body)


func _on_body(b: Node) -> void:
	if not (b is Kart):
		return
	var k := b as Kart
	var now := Time.get_ticks_msec()
	if _cool.get(k, 0) > now:
		return
	_cool[k] = now + 400
	k.boost("pad", 1.15)
	Fx.burst("ring", global_position + Vector3.UP * 0.3, Vector3.UP, Color(1.0, 0.7, 0.2), 1.2)
	if not k.is_player:
		Audio.play_at("boost_pad", global_position, -5.0)
