extends Node
## xvfb-run -a godot --path . res://tools/tests/scene_shot.tscn -- --scene=res://scenes/main_menu.tscn --t=3 --out=/tmp/x --press
var scene := "res://scenes/main_menu.tscn"
var t := 3.0
var out := "/tmp/scene"
var press := false
var _el := 0.0
var _pressed := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		match kv[0]:
			"scene": scene = kv[1]
			"t": t = float(kv[1])
			"out": out = kv[1]
			"press": press = true
	get_tree().root.add_child.call_deferred((load(scene) as PackedScene).instantiate())


func _process(dt: float) -> void:
	_el += dt
	if press and not _pressed and _el > t * 0.4:
		_pressed = true
		var e := InputEventAction.new()
		e.action = "ui_accept"
		e.pressed = true
		Input.parse_input_event(e)
	if _el >= t:
		get_viewport().get_texture().get_image().save_png(out + ".png")
		print("saved ", out)
		get_tree().quit()
