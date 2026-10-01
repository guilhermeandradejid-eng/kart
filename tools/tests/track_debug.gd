extends Node
## Bisect rendering artefacts on the track: one run, several shots, each with a
## different set of node groups hidden.
##   xvfb-run -a godot --path . res://tools/tests/track_debug.tscn -- --s=470 --yaw=90 --out=/tmp/dbg
var s := 470.0
var yaw := 0.0
var out := "/tmp/dbg"
var steps: Array = []   # [label, Callable]
var track: Track
var cam: Camera3D
var _frame := 0
var _i := 0
var views := [0, 1, 2, 3, 4]
var decor := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		match kv[0]:
			"s": s = float(kv[1])
			"yaw": yaw = float(kv[1])
			"out": out = kv[1]
			"fx": Game.set_meta("debug_fx", kv[1])
			"views": views = Array(kv[1].split(",")).map(func(x): return int(x))
			"decor": decor = true
	track = Track.new()
	add_child(track)
	track.load_track(Game.track_id, true)
	var t := track.transform_at(track.data.start_s + s, 0.0, 1.4)
	cam = Camera3D.new()
	cam.fov = 70
	add_child(cam)
	cam.global_transform = t
	cam.rotate_y(deg_to_rad(yaw))
	var prefixes := {}
	for c in track.get_node("Decor").get_children():
		var p := String(c.name).split("_")[0]
		prefixes[p] = true
	print("decor prefixes: ", prefixes.keys())
	track.get_node("Decor").visible = decor
	for k in views:
		steps.append(["view%d" % k, _view.bind(k)])


func _process(_dt: float) -> void:
	_frame += 1
	if _frame < 8:
		return
	_frame = 0
	if _i > 0:
		var p := "%s_%s.png" % [out, steps[_i - 1][0]]
		get_viewport().get_texture().get_image().save_png(p)
		print("saved ", p)
	if _i >= steps.size():
		get_tree().quit()
		return
	steps[_i][1].call()
	_i += 1


func _show_only_decor() -> void:
	track.get_node("Decor").visible = true
	track.get_node("Geometry").visible = false


func _view(k: int) -> void:
	for mi in track.get_node("Geometry").find_children("*", "MeshInstance3D", true, false):
		var mat = mi.get_active_material(0)
		if mat is ShaderMaterial and mat.shader.resource_path.ends_with("terrain.gdshader"):
			mat.set_shader_parameter("debug_view", k)
