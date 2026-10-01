class_name JumpRamp
extends Area3D
## Invisible trigger on the lip of a dash ramp: launches karts over the gap
## with enough speed and lift to clear it, opening the trick window.

var width := 16.0


func _ready() -> void:
	collision_layer = 4
	collision_mask = 2
	monitorable = false
	var cs := CollisionShape3D.new()
	var bx := BoxShape3D.new()
	bx.size = Vector3(width + 2.0, 3.0, 3.0)
	cs.shape = bx
	cs.position.y = 1.0
	add_child(cs)
	body_entered.connect(_on_body)


func _on_body(b: Node) -> void:
	if b is Kart:
		var k := b as Kart
		if k.speed > 4.0:
			k.launch(9.5, 30.0)
			k.boost("pad", 0.6)
