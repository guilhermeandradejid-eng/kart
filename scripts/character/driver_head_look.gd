class_name DriverHeadLook
extends SkeletonModifier3D
## Additive head/neck aim on top of the animation: yaw/pitch targets are eased
## (slow in/out) so the driver looks into corners ahead of the kart and glances
## at rivals. Split 40/60 between neck and head for a natural arc.

var target_yaw := 0.0
var target_pitch := 0.0
var speed := 5.0
var _yaw := 0.0
var _pitch := 0.0
var _head := -1
var _neck := -1


func _process_modification_with_delta(delta: float) -> void:
	var sk := get_skeleton()
	if sk == null:
		return
	if _head < 0:
		_head = sk.find_bone("head")
		_neck = sk.find_bone("neck")
		if _head < 0:
			return
	var k := 1.0 - exp(-delta * speed)
	_yaw = lerpf(_yaw, clampf(target_yaw, -0.9, 0.9), k)
	_pitch = lerpf(_pitch, clampf(target_pitch, -0.4, 0.4), k)
	if _neck >= 0:
		var qn := sk.get_bone_pose_rotation(_neck)
		sk.set_bone_pose_rotation(_neck, qn * Quaternion(Vector3.UP, _yaw * 0.4))
	var qh := sk.get_bone_pose_rotation(_head)
	sk.set_bone_pose_rotation(_head, qh * Quaternion(Vector3.UP, _yaw * 0.6) * Quaternion(Vector3.RIGHT, _pitch))
