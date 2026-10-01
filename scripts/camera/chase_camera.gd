class_name ChaseCamera
extends Camera3D
## Chase camera with weight: spring-damped follow that lags the kart's yaw
## (so drifts read), swings wide on drifts, FOV that breathes with speed and
## kicks on boosts, trauma shake, landing dips, look-back, wall avoidance, and
## scripted modes for the intro fly-over and the finish orbit.

enum Mode { CHASE, INTRO, ORBIT, FREE }

var target: Kart
var mode := Mode.CHASE
var base_fov := 70.0
var dist := 3.35
var height := 1.28
var _roll := 0.0
var _pull := 0.0
var _pos := Vector3.ZERO
var _off := Vector3.ZERO
var _anchor_y := 0.0
var _vel := Vector3.ZERO
var _look := Vector3.ZERO
var _yaw_dir := Vector3.FORWARD
var _fov_kick := 0.0
var _fov_kick_v := 0.0
var _dip := 0.0
var _dip_v := 0.0
var _noise := FastNoiseLite.new()
var _t := 0.0
var _intro_points: Array = []
var _intro_t := 0.0
var _intro_len := 6.0
var _orbit_angle := 0.0
var _swing := 0.0


func _ready() -> void:
	_noise.frequency = 1.6
	fov = base_fov
	near = 0.08
	far = 1600.0
	current = true


func follow(k: Kart, snap := true) -> void:
	if target and target.boosted.is_connected(_on_boost):
		target.boosted.disconnect(_on_boost)
		target.landed.disconnect(_on_land)
	target = k
	target.boosted.connect(_on_boost)
	target.landed.connect(_on_land)
	if snap:
		_yaw_dir = k.forward()
		_pos = _desired()
		_off = _pos - k.global_position
		_vel = Vector3.ZERO
		_anchor_y = k.global_position.y
		_look = k.global_position + Vector3.UP
		global_position = _pos


func _on_boost(kind: String, _d: float) -> void:
	_fov_kick_v += 55.0 if kind in ["mini3", "rocket", "pad", "item"] else 35.0


func _on_land(strength: float) -> void:
	_dip_v -= clampf(strength * 0.12, 0.2, 2.0)


func play_intro(points: Array, duration := 6.0) -> void:
	## points: Array of [camera_pos, look_at] pairs (a spline through them).
	_intro_points = points
	_intro_len = duration
	_intro_t = 0.0
	mode = Mode.INTRO


func orbit(k: Kart) -> void:
	target = k
	mode = Mode.ORBIT
	_orbit_angle = atan2(global_position.x - k.global_position.x, global_position.z - k.global_position.z)


func _desired() -> Vector3:
	var k := target
	var back := -_yaw_dir
	var sp := k.speed_ratio()
	var d := dist + sp * 0.55 + _pull
	var h := height + sp * 0.12 + _pull * 0.25
	if k.controls.look_back:
		back = -back
		d *= 0.95
	var side := k.global_basis.x * _swing
	return k.global_position + back * d + Vector3.UP * h + side


func _physics_process(dt: float) -> void:
	_t += dt
	match mode:
		Mode.CHASE:
			if target:
				_chase(dt)
		Mode.INTRO:
			_intro(dt)
		Mode.ORBIT:
			_orbit(dt)
	_apply_shake(dt)


func _chase(dt: float) -> void:
	var k := target
	# heading we follow: kart forward, biased toward the velocity (drift reads)
	var f := k.forward()
	f.y *= 0.4
	f = f.normalized()
	var v := k.velocity
	v.y = 0.0
	if v.length() > 4.0 and k.speed > 0.0:
		f = f.slerp(v.normalized(), 0.35).normalized()
	var yaw_speed := 4.5 if k.grounded else 2.0
	_yaw_dir = _yaw_dir.slerp(f, 1.0 - exp(-dt * yaw_speed)).normalized()
	# swing wide on drifts (show the outside of the corner)
	var swing_t := -k.drift_dir * 0.9 if k.drifting else 0.0
	_swing = lerpf(_swing, swing_t, 1.0 - exp(-dt * 2.5))
	# turbo pulls the camera back (CTR), drift/steer rolls it slightly (dutch)
	_pull = lerpf(_pull, 0.75 if k.boost_time > 0.0 else 0.0, 1.0 - exp(-dt * (3.0 if k.boost_time > 0.0 else 1.8)))
	var roll_t := -k.steer_smooth * 0.022 * k.speed_ratio() + (k.drift_dir * 0.045 if k.drifting else 0.0)
	_roll = lerpf(_roll, roll_t, 1.0 - exp(-dt * 4.0))
	var desired := _desired()
	# wall / terrain avoidance
	var look_from := k.global_position + Vector3.UP * 1.2
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(look_from, desired, 1)
	q.exclude = [k.get_rid()]
	var hit := space.intersect_ray(q)
	if not hit.is_empty() and not (hit.collider as Object).get_meta("surface", "") in ["wall"]:
		desired = hit.position + (look_from - desired).normalized() * 0.4
	# critically damped spring on the OFFSET from the kart (no lag along the
	# direction of travel, smooth swing when the heading changes)
	var anchor := k.global_position
	_anchor_y = lerpf(_anchor_y, anchor.y, 1.0 - exp(-dt * (12.0 if k.grounded else 3.5)))
	anchor.y = _anchor_y
	var w := 9.0
	var acc := ((desired - k.global_position) - _off) * w * w - _vel * 2.0 * w
	_vel += acc * dt
	_off += _vel * dt
	_pos = anchor + _off
	# vertical lag while airborne keeps jumps readable
	var look_t := k.global_position + Vector3.UP * (0.78 + _dip * 0.3) + _yaw_dir * (4.2 + k.speed_ratio() * 2.5)
	if k.controls.look_back:
		look_t = k.global_position + Vector3.UP * 1.1 - _yaw_dir * 3.0
	_look = look_t
	# landing dip spring
	_dip_v += (-120.0 * _dip - 14.0 * _dip_v) * dt
	_dip += _dip_v * dt
	global_position = _pos + Vector3.UP * _dip * 0.35
	look_at(_look, Vector3.UP)
	rotate_object_local(Vector3.FORWARD, _roll)
	# FOV: speed breathing + boost kick
	_fov_kick_v += (-90.0 * _fov_kick - 11.0 * _fov_kick_v) * dt
	_fov_kick += _fov_kick_v * dt
	var target_fov := base_fov + k.speed_ratio() * 8.0 + (8.0 if k.boost_time > 0.0 else 0.0)
	fov = lerpf(fov, target_fov, 1.0 - exp(-dt * 4.0)) + _fov_kick * 0.35
	fov = clampf(fov, 55.0, 110.0)


func _intro(dt: float) -> void:
	if _intro_points.size() < 2:
		mode = Mode.CHASE
		return
	_intro_t += dt
	var u := clampf(_intro_t / _intro_len, 0.0, 1.0)
	var e := u * u * (3.0 - 2.0 * u)
	var seg := e * (_intro_points.size() - 1)
	var i := mini(int(seg), _intro_points.size() - 2)
	var t := seg - i
	var a: Array = _intro_points[i]
	var b: Array = _intro_points[i + 1]
	global_position = (a[0] as Vector3).lerp(b[0], t)
	look_at((a[1] as Vector3).lerp(b[1], t), Vector3.UP)
	fov = base_fov - 8.0
	if u >= 1.0:
		mode = Mode.CHASE
		if target:
			follow(target, true)


func _orbit(dt: float) -> void:
	if target == null:
		return
	_orbit_angle += dt * 0.35
	var c := target.global_position
	var p := c + Vector3(sin(_orbit_angle), 0, cos(_orbit_angle)) * 5.2 + Vector3.UP * 1.9
	global_position = global_position.lerp(p, 1.0 - exp(-dt * 3.0))
	look_at(c + Vector3.UP * 0.9, Vector3.UP)
	fov = lerpf(fov, 55.0, 1.0 - exp(-dt * 2.0))


func _apply_shake(_dt: float) -> void:
	var tr := Juice.trauma
	if tr <= 0.001:
		return
	var s := tr * tr
	var o := Vector3(_noise.get_noise_2d(_t * 60.0, 0.0), _noise.get_noise_2d(0.0, _t * 60.0), 0.0) * s * 0.35
	global_position += global_basis * o
	rotate_object_local(Vector3.FORWARD, _noise.get_noise_2d(_t * 50.0, 99.0) * s * 0.06)
