class_name Kart
extends CharacterBody3D
## Arcade kart physics + gameplay state (Mario Kart / CTR feel).
## Controllers (PlayerController / AIController) write `controls` every physics
## frame; presentation (KartFX, KartAudio, Driver) only READS this state and
## listens to the signals, so gameplay stays deterministic and testable.
##
## Model: scalar forward speed + lateral slip + vertical velocity, heading
## integrated from steering, body aligned to the ground normal, collisions via
## move_and_slide (walls glance, karts trade momentum by weight).

signal hopped
signal landed(strength: float)
signal drift_started(dir: int)
signal drift_tier(tier: int)
signal drift_ended(tier: int)
signal boosted(kind: String, duration: float)
signal bumped(strength: float, point: Vector3, normal: Vector3, other: Node)
signal spun_out(kind: String)
signal item_changed(item: String, rolling: bool)
signal shells_changed(count: int)
signal trick(kind: String)
signal respawn_started
signal respawned
signal rocket(result: int)   # 1 = rocket start, -1 = burnout

class Controls:
	var throttle := 0.0
	var brake := 0.0
	var steer := 0.0           # -1 left .. +1 right
	var drift := false
	var drift_pressed := false
	var item_pressed := false
	var look_back := false

	func clear() -> void:
		throttle = 0.0
		brake = 0.0
		steer = 0.0
		drift = false
		drift_pressed = false
		item_pressed = false
		look_back = false

const GRAVITY := 34.0
const DRIFT_TIERS := [0.85, 1.8, 3.0]
const MINI_TURBO := [0.7, 1.15, 1.7]
const SURFACE_GRIP := {"road": 1.0, "wood": 1.0, "grass": 0.0, "sand": 0.0}
const MAX_SHELLS := 10

var controls := Controls.new()
var config: KartConfig
var tuning := {}
var model: KartModel
var driver: Driver
var racer_name := "Guará"
var is_player := false
var grid_index := 0
var race: Node = null              # RaceManager (for items / respawn); optional
var locked := true
var finished := false
var speed_mult := 1.0              # difficulty x rubber band
var shells := 0
var item := ""
var item_rolling := 0.0

# --- physics state ---
var speed := 0.0
var lateral := 0.0
var vertical := 0.0
var knock := Vector3.ZERO
var grounded := true
var was_grounded := true
var ground_normal := Vector3.UP
var surface := "road"
var air_time := 0.0
var launch_speed := 0.0
var launched := false
var drifting := false
var drift_dir := 0
var drift_charge := 0.0
var drift_tier_level := 0
var hop_time := 0.0
var drift_wait := 0.0
var boost_time := 0.0
var boost_kind := ""
var spin_time := 0.0
var spin_total := 0.0
var trick_window := 0.0
var tricked := false
var invuln := 0.0
var visual_yaw := 0.0
var steer_smooth := 0.0
var accel_signal := 0.0            # +accelerating / -braking (for body pitch)
var respawning := 0.0
var last_safe := Transform3D()
var _bump_cool := 0.0
var _rocket_press := -1.0
var _stall := 0.0
var _countdown := -1.0
var _prev_vel := Vector3.ZERO
var distance_travelled := 0.0


func setup(cfg: KartConfig, player := false, variant := 0) -> void:
	config = cfg
	is_player = player
	tuning = KartParts.tuning_for(cfg)
	motion_mode = CharacterBody3D.MOTION_MODE_GROUNDED
	floor_max_angle = deg_to_rad(52.0)
	floor_snap_length = 0.7
	floor_constant_speed = true
	floor_stop_on_slope = true
	max_slides = 5
	wall_min_slide_angle = deg_to_rad(10.0)
	safe_margin = 0.02
	collision_layer = 2
	collision_mask = 1 | 2
	var shape := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.62
	cap.height = 2.1
	shape.shape = cap
	shape.rotation.x = PI / 2
	shape.position = Vector3(0, 0.64, 0.05)
	add_child(shape)
	model = KartModel.new(cfg)
	model.name = "Model"
	add_child(model)
	model.build(cfg)
	driver = Driver.new(variant)
	driver.name = "Driver"
	model.driver_mount.add_child(driver)
	last_safe = global_transform


func _ready() -> void:
	last_safe = global_transform


# ------------------------------------------------------------------ helpers

func forward() -> Vector3:
	return -global_basis.z


func top_speed() -> float:
	var t: float = tuning.max_speed * speed_mult * (1.0 + shells * 0.012)
	var offroad: bool = SURFACE_GRIP.get(surface, 1.0) < 0.5 and grounded
	if offroad and boost_time <= 0.0:
		t *= tuning.offroad
	if boost_time > 0.0:
		t *= 1.32 if boost_kind != "trick" else 1.2
	if drifting:
		t *= 0.985
	return t


func speed_ratio() -> float:
	return clampf(absf(speed) / (tuning.max_speed * 1.0), 0.0, 1.5)


func is_offroad() -> bool:
	return grounded and SURFACE_GRIP.get(surface, 1.0) < 0.5


# ------------------------------------------------------------------ main loop

func _physics_process(dt: float) -> void:
	if tuning.is_empty():
		return
	_timers(dt)
	if respawning > 0.0:
		_respawn_tick(dt)
		return
	var steer_in := 0.0 if (spin_time > 0.0 or _stall > 0.0) else controls.steer
	steer_smooth = move_toward(steer_smooth, steer_in, dt * 7.0)
	if locked:
		_countdown_tick(dt)
	else:
		_drive(dt)
	_integrate(dt)
	_post_move(dt)
	controls.drift_pressed = false
	controls.item_pressed = false


func _timers(dt: float) -> void:
	boost_time = maxf(boost_time - dt, 0.0)
	if boost_time <= 0.0:
		boost_kind = ""
	hop_time = maxf(hop_time - dt, 0.0)
	drift_wait = maxf(drift_wait - dt, 0.0)
	trick_window = maxf(trick_window - dt, 0.0)
	invuln = maxf(invuln - dt, 0.0)
	_bump_cool = maxf(_bump_cool - dt, 0.0)
	_stall = maxf(_stall - dt, 0.0)
	knock *= exp(-dt * 4.5)
	if item_rolling > 0.0:
		item_rolling -= dt
		if item_rolling <= 0.0:
			item_changed.emit(item, false)
	if spin_time > 0.0:
		spin_time -= dt
		var k := 1.0 - clampf(spin_time / spin_total, 0.0, 1.0)
		visual_yaw = -TAU * 2.0 * (1.0 - pow(1.0 - k, 2.2))
		if spin_time <= 0.0:
			visual_yaw = 0.0


func _drive(dt: float) -> void:
	var top := top_speed()
	var throttle := controls.throttle
	var brake := controls.brake
	if spin_time > 0.0 or _stall > 0.0 or finished and not is_player and false:
		throttle = 0.0
	if spin_time > 0.0:
		speed = move_toward(speed, 0.0, dt * 24.0)
	elif boost_time > 0.0:
		speed = move_toward(speed, top, dt * (top / tuning.accel_time) * 6.0)
	elif brake > 0.3 and throttle < 0.3:
		if speed > 0.5:
			speed = move_toward(speed, 0.0, dt * 34.0 * brake)
		else:
			speed = move_toward(speed, -9.0, dt * 14.0)
	elif throttle > 0.05:
		if speed > top:
			speed = move_toward(speed, top, dt * (22.0 if is_offroad() else 9.0))
		else:
			var k: float = 2.3 / tuning.accel_time
			speed += (top * throttle - speed) * (1.0 - exp(-k * dt))
			if speed < 0.0:
				speed = move_toward(speed, 0.0, dt * 30.0)
	else:
		speed = move_toward(speed, 0.0, dt * (5.0 + (14.0 if is_offroad() else 0.0)))
		if speed > top:
			speed = move_toward(speed, top, dt * 18.0)
	accel_signal = lerpf(accel_signal, (throttle - brake * 1.5) if spin_time <= 0.0 else -1.0, 1.0 - exp(-dt * 6.0))

	# --- drift / hop / tricks
	if controls.drift_pressed:
		if grounded and hop_time <= 0.0 and not drifting and speed > 6.0 and spin_time <= 0.0:
			_hop()
		elif not grounded and trick_window > 0.0 and not tricked:
			_do_trick()
	if drifting:
		_drift_tick(dt)
	elif controls.drift and grounded and speed > 7.0 and drift_wait > 0.0 and absf(controls.steer) > 0.35 and spin_time <= 0.0:
		_start_drift(int(signf(controls.steer)))

	# --- items
	if controls.item_pressed and item != "" and item_rolling <= 0.0 and spin_time <= 0.0 and race:
		var used := item
		item = ""
		item_changed.emit("", false)
		race.use_item(self, used)


func _countdown_tick(dt: float) -> void:
	speed = 0.0
	lateral = 0.0
	if _countdown < 0.0:
		return
	if controls.throttle > 0.5 and _rocket_press < 0.0:
		_rocket_press = _countdown
	elif controls.throttle < 0.2:
		_rocket_press = -1.0


func set_countdown(t: float) -> void:
	_countdown = t


## Called by the race when the lights go green.
func release() -> void:
	locked = false
	_countdown = -1.0
	if _rocket_press >= 0.0 and controls.throttle > 0.5:
		if _rocket_press <= 1.05 and _rocket_press >= 0.12:
			speed = tuning.max_speed * 0.55
			boost("rocket", 1.25)
			rocket.emit(1)
		elif _rocket_press > 1.5:
			_stall = 0.9
			rocket.emit(-1)


func _hop() -> void:
	hop_time = 0.32
	drift_wait = 0.42
	vertical = 5.2
	grounded = false
	hopped.emit()


func _start_drift(dir: int) -> void:
	drifting = true
	drift_dir = dir
	drift_charge = 0.0
	drift_tier_level = 0
	drift_wait = 0.0
	drift_started.emit(dir)


func _drift_tick(dt: float) -> void:
	if not controls.drift or speed < 5.5 or spin_time > 0.0:
		_end_drift(true)
		return
	if not grounded:
		return
	var inward := controls.steer * drift_dir
	drift_charge += dt * (0.75 + 0.65 * maxf(inward, 0.0)) * (0.7 if is_offroad() else 1.0)
	var tier := 0
	for i in DRIFT_TIERS.size():
		if drift_charge >= DRIFT_TIERS[i]:
			tier = i + 1
	if tier != drift_tier_level:
		drift_tier_level = tier
		drift_tier.emit(tier)


func _end_drift(reward: bool) -> void:
	var tier := drift_tier_level
	drifting = false
	drift_dir = 0
	drift_charge = 0.0
	drift_tier_level = 0
	drift_ended.emit(tier)
	if reward and tier > 0:
		boost("mini%d" % tier, MINI_TURBO[tier - 1] * tuning.turbo)


func boost(kind: String, duration: float) -> void:
	var fresh := boost_time <= 0.05
	boost_time = maxf(boost_time, duration)
	boost_kind = kind
	speed = maxf(speed, tuning.max_speed * speed_mult * (1.12 if fresh else 1.0))
	boosted.emit(kind, duration)


func _do_trick() -> void:
	tricked = true
	vertical += 1.6
	trick.emit(["a", "b"][randi() % 2])


func spin_out(kind := "banana", duration := 1.25) -> bool:
	if invuln > 0.0 or spin_time > 0.0 or respawning > 0.0:
		return false
	if drifting:
		_end_drift(false)
	boost_time = 0.0
	spin_time = duration
	spin_total = duration
	speed *= 0.55
	invuln = duration + 0.6
	var lost := mini(shells, 3)
	if lost > 0:
		add_shells(-lost)
	spun_out.emit(kind)
	return true


func add_shells(n: int) -> void:
	var before := shells
	shells = clampi(shells + n, 0, MAX_SHELLS)
	if shells != before:
		shells_changed.emit(shells)


func give_item(it: String, roll := 1.4) -> void:
	item = it
	item_rolling = roll
	item_changed.emit(it, true)


# ------------------------------------------------------------------ integration

func _integrate(dt: float) -> void:
	var up := global_basis.y
	# --- yaw
	var yaw_rate := 0.0
	if not locked and spin_time <= 0.0:
		var sp := absf(speed)
		var low := clampf(sp / 11.0, 0.0, 1.0)
		var high := 1.0 - 0.22 * clampf((sp - 22.0) / 10.0, 0.0, 1.0)
		if drifting:
			var inward := controls.steer * drift_dir
			# steering modulates the drift: outward ~ straight, neutral ~30 m, inward tight
			yaw_rate = drift_dir * tuning.turn_rate * (0.46 + 0.44 * inward) * low
		else:
			yaw_rate = tuning.turn_rate * steer_smooth * low * high * signf(speed if absf(speed) > 0.3 else 1.0)
		if not grounded:
			yaw_rate *= 0.4
	global_basis = Basis(up, -yaw_rate * dt) * global_basis
	# --- align to ground
	var target_up := ground_normal if grounded else Vector3.UP
	var rate := 14.0 if grounded else 3.0
	var q := Quaternion(global_basis.y.normalized(), target_up.normalized())
	global_basis = (Basis(Quaternion.IDENTITY.slerp(q, 1.0 - exp(-dt * rate))) * global_basis).orthonormalized()
	# --- visual drift angle
	var target_vy := 0.0
	if drifting:
		target_vy = -drift_dir * (0.42 + 0.12 * controls.steer * drift_dir)
	if spin_time <= 0.0:
		visual_yaw = lerpf(visual_yaw, target_vy, 1.0 - exp(-dt * 8.0))
	# --- lateral slip
	if drifting:
		lateral = lerpf(lateral, -drift_dir * absf(speed) * 0.2, 1.0 - exp(-dt * 5.0))
	else:
		lateral *= exp(-dt * tuning.grip)
	# --- velocity
	var fwd := forward()
	if grounded:
		var n := ground_normal
		var f_g := (fwd - n * fwd.dot(n)).normalized()
		var r_g := f_g.cross(n).normalized()
		velocity = f_g * speed + r_g * lateral + knock - n * 1.5
		vertical = 0.0
	else:
		vertical -= GRAVITY * (0.68 if launched else 1.0) * dt
		var f_h := Vector3(fwd.x, 0.0, fwd.z).normalized()
		var r_h := f_h.cross(Vector3.UP)
		velocity = f_h * speed + r_h * lateral + Vector3.UP * vertical + knock
	up_direction = ground_normal if grounded else Vector3.UP
	_prev_vel = velocity
	var before := global_position
	move_and_slide()
	distance_travelled += (global_position - before).length()


func _post_move(dt: float) -> void:
	was_grounded = grounded
	var on_floor := is_on_floor()
	if vertical > 0.5 and not was_grounded:
		on_floor = false
	var hit := _probe()
	if on_floor:
		grounded = true
		var fn := get_floor_normal()
		ground_normal = ground_normal.slerp(fn, 1.0 - exp(-dt * 18.0)).normalized()
	else:
		# near-ground probe keeps us glued over tiny gaps (seams, curbs)
		if hit and vertical <= 0.0 and hit.distance < 0.28 and hop_time <= 0.0:
			grounded = true
			ground_normal = ground_normal.slerp(hit.normal, 1.0 - exp(-dt * 18.0)).normalized()
		else:
			grounded = false
	if hit:
		surface = hit.surface
	if grounded:
		if not was_grounded:
			_on_land()
		air_time = 0.0
		if surface in ["road", "wood"] and spin_time <= 0.0 and _is_safe_spot():
			last_safe = global_transform
	else:
		if was_grounded:
			# took off: keep the ramp's vertical component
			vertical = maxf(_prev_vel.y, vertical)
			launch_speed = vertical
			if vertical > 3.0:
				trick_window = 0.55
				tricked = false
		air_time += dt
	# --- collisions
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var n := c.get_normal()
		if n.dot(up_direction) > 0.55:
			continue
		var other := c.get_collider()
		if other is Kart:
			_bump_kart(other as Kart, n, c.get_position())
		else:
			_bump_wall(n, c.get_position())
	# --- fell off the world
	var wl := -1.2
	if race and race.has_method("water_level"):
		wl = race.water_level() - 1.2
	if global_position.y < wl or global_position.y < -40.0:
		start_respawn()


func _probe() -> Dictionary:
	var space := get_world_3d().direct_space_state
	var from := global_position + global_basis.y * 0.6
	var to := from - global_basis.y * 1.5
	var q := PhysicsRayQueryParameters3D.create(from, to, 1)
	q.exclude = [get_rid()]
	var r := space.intersect_ray(q)
	if r.is_empty():
		return {}
	var s := "road"
	var col: Object = r.collider
	if col and col.has_meta("surface"):
		s = col.get_meta("surface")
	return {"distance": from.distance_to(r.position) - 0.6, "normal": r.normal, "surface": s}


func _is_safe_spot() -> bool:
	return absf(lateral) < 6.0 and ground_normal.dot(Vector3.UP) > 0.8


## Dash ramp: guaranteed airtime (MK-style jump with a trick window).
func launch(vy: float, min_speed: float) -> void:
	if respawning > 0.0:
		return
	speed = maxf(speed, min_speed)
	vertical = maxf(vertical, vy)
	grounded = false
	launched = true
	trick_window = 0.7
	tricked = false
	global_position += Vector3.UP * 0.15


func _on_land() -> void:
	launched = false
	var strength := maxf(-vertical, 0.0)
	if air_time > 0.12 or strength > 2.0:
		landed.emit(strength)
	if tricked:
		tricked = false
		boost("trick", 0.9)
	vertical = 0.0


func _bump_wall(n: Vector3, point: Vector3) -> void:
	var impact := -_prev_vel.dot(n)
	if impact < 1.5 or _bump_cool > 0.0:
		return
	_bump_cool = 0.18
	var fwd := forward()
	var head_on := absf(fwd.dot(n))
	speed *= 1.0 - clampf(head_on * 0.75 + impact / 60.0, 0.05, 0.8)
	knock += n * clampf(impact * 0.45, 2.0, 9.0)
	lateral *= 0.3
	if drifting and impact > 7.0:
		_end_drift(false)
	bumped.emit(impact, point, n, null)


func _bump_kart(other: Kart, n: Vector3, point: Vector3) -> void:
	if _bump_cool > 0.0:
		return
	var rel := (_prev_vel - other.velocity).dot(-n)
	var strength := maxf(rel, 0.0) + 3.0
	var w1: float = tuning.weight
	var w2: float = other.tuning.weight
	var mine := w2 / (w1 + w2)
	knock += n * strength * mine * 1.3
	other.knock -= n * strength * (1.0 - mine) * 1.3
	speed *= 1.0 - 0.12 * mine
	_bump_cool = 0.25
	other._bump_cool = 0.25
	bumped.emit(strength, point, n, other)
	other.bumped.emit(strength, point, -n, self)


# ------------------------------------------------------------------ respawn

func start_respawn() -> void:
	if respawning > 0.0:
		return
	respawning = 1.3
	if drifting:
		_end_drift(false)
	speed = 0.0
	lateral = 0.0
	vertical = 0.0
	knock = Vector3.ZERO
	respawn_started.emit()


func _respawn_tick(dt: float) -> void:
	var prev := respawning
	respawning -= dt
	velocity = Vector3.ZERO
	if prev > 0.55 and respawning <= 0.55:
		var t := last_safe
		if race and race.has_method("respawn_transform"):
			t = race.respawn_transform(self)
		global_transform = t
		global_position += t.basis.y * 1.6
		visual_yaw = 0.0
	if respawning <= 0.0:
		respawning = 0.0
		invuln = 1.8
		grounded = false
		vertical = -1.0
		respawned.emit()


func is_boosting() -> bool:
	return boost_time > 0.0
