extends SceneTree
## godot --headless --path . -s res://tools/tests/check_scripts.gd
## Loads every script so parse/type errors surface in one pass.
func _init() -> void:
	var bad := 0
	for f in _walk("res://scripts"):
		var s := load(f)
		if s == null:
			bad += 1
			printerr("FAILED: ", f)
	print("checked scripts, failures: ", bad)
	quit(1 if bad else 0)

func _walk(dir: String) -> Array:
	var out := []
	var d := DirAccess.open(dir)
	for f in d.get_files():
		if f.ends_with(".gd"):
			out.append(dir + "/" + f)
	for sub in d.get_directories():
		out += _walk(dir + "/" + sub)
	return out
