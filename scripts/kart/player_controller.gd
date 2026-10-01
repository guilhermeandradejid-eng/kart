class_name PlayerController
extends Node
## Reads InputMap actions into the kart's controls (runs before the kart).

var kart: Kart
var enabled := true


func _ready() -> void:
	process_physics_priority = -10


func _physics_process(_dt: float) -> void:
	if kart == null:
		return
	var c := kart.controls
	if not enabled:
		c.clear()
		return
	c.throttle = Input.get_action_strength("accelerate")
	c.brake = Input.get_action_strength("brake")
	c.steer = clampf(Input.get_action_strength("steer_right") - Input.get_action_strength("steer_left"), -1.0, 1.0)
	c.drift = Input.is_action_pressed("drift")
	if Input.is_action_just_pressed("drift"):
		c.drift_pressed = true
	if Input.is_action_just_pressed("item"):
		c.item_pressed = true
	c.look_back = Input.is_action_pressed("look_back")
