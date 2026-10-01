class_name AIController
extends Node
## Rival driver brain. Follows a precomputed racing line (outside-apex-outside)
## with a personal lane bias, manages speed from upcoming curvature, drifts
## through long corners for mini-turbos, dodges hazards and karts, uses items
## tactically and recovers when stuck. `skill` 0..1 scales everything.

static var _lines := {}

var kart: Kart
var track: Track
var race: Node
var skill := 0.75
var lane := 0.0
var hint := -1
var _line: PackedFloat32Array
var _stuck := 0
var _prog_t := 0.0
var _prog_s := 0.0
var _reverse := 0.0
var _item_think := 0.0
var _max_tier := 2
var _rng := RandomNumberGenerator.new()
var _wobble := 0.0
var _drift_cool := 0.0
var _rocket_at := 0.0


func setup(k: Kart, t: Track, r: Node, sk: float, seed_v: int) -> void:
	kart = k
	track = t
	race = r
	skill = sk
	_rng.seed = seed_v
	lane = _rng.randf_range(-1.0, 1.0)
	_max_tier = 3 if skill > 0.85 else (2 if skill > 0.6 else 1)
	_rocket_at = _rng.randf_range(0.2, 0.95) if _rng.randf() < skill else _rng.randf_range(-0.3, 0.1)
	process_physics_priority = -10
	if not _lines.has(t.id):
		_lines[t.id] = _compute_line(t)
	_line = _lines[t.id]


static func _compute_line(t: Track) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(t.n)
	for i in t.n:
		var s := t.svals[i]
		var here := t.curvature_ahead(s - 8.0, 16.0)
		var ahead := t.curvature_ahead(s + 18.0, 26.0)
		var o := clampf(-here * 230.0 + ahead * 110.0, -0.62, 0.62)
		out[i] = o * t.width[i] * 0.5
	# smooth
	for it in 6:
		var cp := out.duplicate()
		for i in t.n:
			out[i] = (cp[(i - 1 + t.n) % t.n] + cp[i] * 2.0 + cp[(i + 1) % t.n]) * 0.25
	return out


func _physics_process(dt: float) -> void:
	if kart == null or track == null:
		return
	var c := kart.controls
	c.clear()
	if kart.locked:
		var left: float = race.countdown_left if race else 9.0
		c.throttle = 1.0 if left < _rocket_at + 0.0 else 0.0
		return
	var loc := track.locate(kart.global_position, hint)
	hint = loc.index
	var s: float = loc.s
	var spd := maxf(kart.speed, 6.0)
	_wobble += dt
	# --- recovery
	if _reverse > 0.0:
		_reverse -= dt
		c.brake = 1.0
		c.steer = -signf(loc.lateral) if absf(loc.lateral) > 1.0 else 1.0
		return
	# progress watchdog: not advancing along the track = stuck (walls, props, terrain)
	_prog_t += dt
	if _prog_t > 1.5:
		var adv := fposmod(s - _prog_s, track.length)
		if adv > track.length * 0.5:
			adv = 0.0
		if adv < 4.0 and kart.spin_time <= 0.0 and kart.respawning <= 0.0:
			_stuck += 1
			if _stuck >= 2:
				_reverse = 0.8
			if _stuck >= 4:
				_stuck = 0
				kart.start_respawn()
		else:
			_stuck = 0
		_prog_t = 0.0
		_prog_s = s
	# --- target on the line
	var look := 7.0 + spd * 0.42
	var fr := track.frame_at(s + look)
	var idx: int = fr.i
	var half: float = fr.w * 0.5
	var bias := lane * 0.28 * half * (1.0 - clampf(absf(fr.c) * 45.0, 0.0, 1.0))
	var sloppy := sin(_wobble * (0.6 + _rng.randf() * 0.01)) * (1.0 - skill) * half * 0.35
	var target_lat := _line[idx] + bias + sloppy
	target_lat += _avoid(s, loc.lateral, look)
	target_lat = clampf(target_lat, -half + 1.2, half - 1.2)
	var target: Vector3 = fr.p + fr.r * target_lat
	var to := target - kart.global_position
	var f := kart.forward()
	var r := kart.global_basis.x
	var ang := atan2(to.dot(r), to.dot(f))
	c.steer = clampf(ang * (2.0 + skill), -1.0, 1.0)
	if absf(loc.lateral) > loc.half_width + 2.5:
		c.steer = clampf(-signf(loc.lateral) * 1.0 + ang, -1.0, 1.0)
	# --- speed
	var k_max := 0.0
	var d := 4.0
	while d < spd * 1.25 + 8.0:
		k_max = maxf(k_max, absf(track.curv[track.index_of_s(s + d)]))
		d += 2.0
	var budget := 20.0 + 14.0 * skill + (12.0 if kart.drifting else 0.0)
	var v_safe := sqrt(budget / maxf(k_max, 0.0008))
	c.throttle = 1.0
	if kart.speed > v_safe * 1.03:
		c.throttle = 0.0
		if kart.speed > v_safe * 1.25:
			c.brake = 0.7
	# --- drift
	_drift_cool = maxf(_drift_cool - dt, 0.0)
	var turn := track.curvature_ahead(s, 26.0, 4.0)
	if kart.drifting:
		c.drift = true
		c.steer = clampf(ang * 3.2, -1.0, 1.0)
		var remaining := absf(track.curvature_ahead(s, 14.0, 2.0))
		var sign_ok := signf(-turn) == float(kart.drift_dir) or absf(turn) < 0.004
		if remaining < 0.0055 or not sign_ok or kart.drift_tier_level >= _max_tier and remaining < 0.012:
			c.drift = false
			_drift_cool = 0.8
	elif _drift_cool <= 0.0 and _good_drift(s, turn) and kart.speed > 15.0 and kart.grounded and _rng.randf() < 0.08 + skill * 0.25:
		c.drift = true
		c.drift_pressed = true
		c.steer = -signf(turn)
	elif kart.drift_wait > 0.0:
		c.drift = true
		c.steer = -signf(turn) if absf(turn) > 0.008 else c.steer
	# --- items
	_item_think -= dt
	if kart.item != "" and kart.item_rolling <= 0.0 and _item_think <= 0.0:
		_item_think = _rng.randf_range(0.3, 0.9)
		if _should_use(kart.item, s, turn):
			c.item_pressed = true


func _good_drift(s: float, turn: float) -> bool:
	## Only drift corners that keep turning the same way for a while (no chicanes).
	if absf(turn) < 0.016:
		return false
	var sg := signf(turn)
	var d := 0.0
	while d < 36.0:
		var c := track.curv[track.index_of_s(s + d)]
		if signf(c) != sg or absf(c) < 0.006:
			return false
		d += 4.0
	return true


func _avoid(s: float, my_lat: float, look: float) -> float:
	var shift := 0.0
	for h in get_tree().get_nodes_in_group("hazards"):
		var hl := track.locate((h as Node3D).global_position, hint)
		var ds := fposmod(hl.s - s, track.length)
		if ds > 1.0 and ds < look + 6.0 and absf(hl.lateral - my_lat) < 2.4:
			shift += (2.6 - absf(hl.lateral - my_lat)) * (1.0 if my_lat >= hl.lateral else -1.0) * (0.4 + skill)
	for k in get_tree().get_nodes_in_group("karts"):
		if k == kart:
			continue
		var kk := k as Kart
		var kl := track.locate(kk.global_position, hint)
		var ds := fposmod(kl.s - s, track.length)
		if ds > 0.5 and ds < 9.0 and absf(kl.lateral - my_lat) < 1.8 and kk.speed < kart.speed:
			shift += (1.9 - absf(kl.lateral - my_lat)) * (1.0 if my_lat >= kl.lateral else -1.0) * 0.8
	return clampf(shift, -4.0, 4.0)


func _should_use(it: String, s: float, turn: float) -> bool:
	match it:
		"pepper":
			return absf(turn) < 0.006 and not kart.is_offroad() or kart.is_offroad() and absf(turn) < 0.012
		"banana":
			for k in get_tree().get_nodes_in_group("karts"):
				if k != kart:
					var kl := track.locate((k as Kart).global_position, hint)
					var ds := fposmod(s - kl.s, track.length)
					if ds > 2.0 and ds < 18.0:
						return true
			return _rng.randf() < 0.15
		"coconut":
			for k in get_tree().get_nodes_in_group("karts"):
				if k != kart:
					var kl := track.locate((k as Kart).global_position, hint)
					var ds := fposmod(kl.s - s, track.length)
					if ds > 4.0 and ds < 45.0:
						return _rng.randf() < 0.5 + skill * 0.4
			return false
	return true
