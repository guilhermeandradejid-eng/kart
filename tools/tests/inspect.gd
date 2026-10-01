extends SceneTree
## godot --headless --path . -s res://tools/tests/inspect.gd -- res://path.glb
func _init():
	var args := OS.get_cmdline_user_args()
	for path in args:
		var ps: PackedScene = load(path)
		var root := ps.instantiate()
		print("== ", path)
		_dump(root, 0)
		var ap := root.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if ap:
			print("anims: ", ap.get_animation_list())
		var sk := root.find_child("*", true, false)
		for n in root.find_children("*", "Skeleton3D", true, false):
			var s := n as Skeleton3D
			var names := []
			for i in s.get_bone_count(): names.append(s.get_bone_name(i))
			print("bones(", s.get_bone_count(), "): ", names)
		root.free()
	quit()
func _dump(n: Node, d: int):
	var extra := ""
	if n is MeshInstance3D:
		var m: Mesh = n.mesh
		var mats := []
		for i in m.get_surface_count(): mats.append(m.surface_get_material(i).resource_name if m.surface_get_material(i) else "-")
		extra = " surfaces=%s" % [mats]
	if n is Node3D and d < 3:
		extra += " pos=%s" % [(n as Node3D).position]
	if d < 4 or n is MeshInstance3D:
		print("  ".repeat(d), n.name, " <", n.get_class(), ">", extra)
	for c in n.get_children(): _dump(c, d + 1)
