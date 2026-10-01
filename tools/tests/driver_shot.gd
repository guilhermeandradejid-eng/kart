extends Node
## Character close-ups in Godot (validates imported clips + AnimationTree):
##   xvfb-run -a godot --path . res://tools/tests/driver_shot.tscn -- --shots=race:0.6,drift:0.5,victory:1.4 --out=/tmp/d
var shots: Array = []
var out := "/tmp/driver"
var room: Showroom
var _i := 0
var _t := 0.0
var _cur := ""
var images: Array[Image] = []


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		if kv[0] == "shots":
			for s in kv[1].split(","):
				var p := s.split(":")
				shots.append([p[0], float(p[1])])
		elif kv[0] == "out":
			out = kv[1]
	room = Showroom.new()
	room.spin = false
	room.cam_target = Vector3(0, 0.78, -0.15)
	room.cam_dist = 2.3
	room.cam_height = 0.35
	room.cam_yaw = PI - 0.45
	add_child(room)
	room.turntable.rotation.y = 0.0


func _process(dt: float) -> void:
	if room.driver == null or room.driver.tree == null:
		return
	if _i >= shots.size():
		_finish()
		return
	var name: String = shots[_i][0]
	if _cur != name:
		_cur = name
		_t = 0.0
		room.driver._state = ""
		match name:
			"race", "countdown", "victory", "lose", "wave", "idle":
				room.driver.set_state(name)
			"steer_l":
				room.driver.set_state("race")
			"steer_r":
				room.driver.set_state("race")
			"drift":
				room.driver.set_state("race")
			_:
				room.driver.set_state("race")
				room.driver.fire(name if name in ["hop", "land", "boost", "hit"] else ("trick" if name.begins_with("trick") else "action"),
					"" if name in ["hop", "land", "boost", "hit"] else ("trick_" + name.substr(6) if name.begins_with("trick") else name))
	var steer := -1.0 if _cur == "steer_l" else (1.0 if _cur == "steer_r" else 0.0)
	room.driver.set_drive(steer, 1.0 if _cur == "drift" else 0.0, -1.0, 0.0, dt)
	_t += dt
	if _t >= shots[_i][1]:
		var img := get_viewport().get_texture().get_image()
		img.resize(640, 360)
		images.append(img)
		_i += 1


func _finish() -> void:
	var cols := 3
	var rows := int(ceil(images.size() / float(cols)))
	var sheet := Image.create(640 * cols, 360 * rows, false, Image.FORMAT_RGBA8)
	for k in images.size():
		var im := images[k]
		im.convert(Image.FORMAT_RGBA8)
		sheet.blit_rect(im, Rect2i(0, 0, 640, 360), Vector2i((k % cols) * 640, (k / cols) * 360))
	sheet.save_png(out + ".png")
	print("saved ", out)
	get_tree().quit()
