extends Node
var d: Driver
var t := 0.0
var phase := 0
func _ready():
	d = Driver.new(0)
	add_child(d)
func _head() -> Vector3:
	var sk := d.skeleton
	return sk.get_bone_global_pose(sk.find_bone("head")).origin
func _process(dt):
	t += dt
	if phase == 0 and t > 0.5:
		print("race head=", _head())
		d.set_state("victory"); phase = 1; t = 0.0
	elif phase == 1 and t > 1.6:
		print("victory head=", _head(), " cur=", d.tree.get("parameters/state/current_state"))
		d.set_state("wave"); phase = 2; t = 0.0
	elif phase == 2 and t > 0.8:
		print("wave head=", _head(), " hand.R=", d.skeleton.get_bone_global_pose(d.skeleton.find_bone("hand.R")).origin)
		get_tree().quit()
