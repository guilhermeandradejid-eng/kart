class_name KartFX
extends Node3D
## Presentation layer for one kart: sprung body (suspension, squash & stretch,
## roll/pitch), wheel spin/steer, engine shake, continuous particles (drift
## sparks by tier, tyre smoke / sand / grass kick-up, boost flames, exhaust
## puffs) and the Guará's animation parameters. Reads Kart state, never writes it.

const TIER_COLORS := [Color(0.9, 0.9, 1.0), Color(0.3, 0.65, 1.0), Color(1.0, 0.55, 0.12), Color(0.85, 0.35, 1.0)]
const SURFACE_DUST := {"road": Color(0.85, 0.85, 0.88), "wood": Color(0.8, 0.7, 0.55),
	"sand": Color(0.95, 0.82, 0.58), "grass": Color(0.45, 0.72, 0.3)}

var kart: Kart
var model: KartModel

# springs
var _bounce := 0.0
var _bounce_v := 0.0
var _squash := 0.0
var _squash_v := 0.0
var _roll := 0.0
var _pitch := 0.0
var _flash := 0.0
var _flash_color := Color.WHITE
var _steer_vis := 0.0
var _t := 0.0

# emitters
var sparks := {}        # "rl"/"rr" -> GPUParticles3D
var glows := {}         # "rl"/"rr" -> MeshInstance3D
var smoke := {}
var kick := {}
var flames: Array[GPUParticles3D] = []
var flame_cones: Array[MeshInstance3D] = []
var puffs: Array[GPUParticles3D] = []
var trail: GPUParticles3D
var scrape: GPUParticles3D
var _tier := 0


func setup(k: Kart) -> void:
	kart = k
	model = k.model
	_build_emitters()
	kart.hopped.connect(_on_hop)
	kart.landed.connect(_on_land)
	kart.boosted.connect(_on_boost)
	kart.bumped.connect(_on_bump)
	kart.spun_out.connect(_on_spin)
	kart.drift_tier.connect(_on_tier)
	kart.drift_started.connect(func(_d): _squash_v -= 1.0)
	kart.trick.connect(_on_trick)
	kart.respawn_started.connect(_on_respawn_start)
	kart.respawned.connect(_on_respawned)
	kart.rocket.connect(_on_rocket)
	model.rebuilt.connect(_rebind_exhausts)


func _build_emitters() -> void:
	for key in ["rl", "rr"]:
		var s := Fx.make_particles({"amount": 40, "lifetime": 0.32, "dir": Vector3(0, 1, 1), "spread": 35.0,
			"vmin": 3.0, "vmax": 7.5, "gravity": Vector3(0, -18, 0), "tex": Fx.tex_spark, "size": Vector2(0.05, 0.22),
			"align": true, "radius": 0.08,
			"ramp": [[0.0, Color(1, 1, 1, 1)], [0.3, Color(1, 1, 1, 1)], [1.0, Color(1, 1, 1, 0)]]})
		s.emitting = false
		add_child(s)
		sparks[key] = s
		var g := MeshInstance3D.new()
		var gm := Fx.particle_mat(Fx.tex_soft, "add").duplicate() as StandardMaterial3D
		gm.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
		g.mesh = Fx.quad(Vector2(0.9, 0.9), gm)
		g.visible = false
		g.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(g)
		glows[key] = g
		var sm := Fx.make_particles({"amount": 40, "lifetime": 1.6, "dir": Vector3(0, 1, 0.5), "spread": 40.0,
			"vmin": 0.8, "vmax": 2.6, "gravity": Vector3(0, 1.4, 0), "damp": 2.2, "tex": Fx.tex_puff, "blend": "mix",
			"size": Vector2(1.25, 1.25), "scale_curve": [[0.0, 0.35], [0.25, 1.0], [1.0, 2.3]], "spin_min": -50.0, "spin_max": 50.0,
			"radius": 0.25, "angle_max": 360.0,
			"ramp": [[0.0, Color(1, 1, 1, 0.0)], [0.08, Color(1, 1, 1, 0.75)], [0.5, Color(1, 1, 1, 0.45)], [1.0, Color(1, 1, 1, 0.0)]]})
		sm.emitting = false
		add_child(sm)
		smoke[key] = sm
		var kc := Fx.make_particles({"amount": 30, "lifetime": 0.7, "dir": Vector3(0, 1.2, 1), "spread": 25.0,
			"vmin": 2.0, "vmax": 5.0, "gravity": Vector3(0, -14, 0), "tex": Fx.tex_puff, "blend": "mix",
			"size": Vector2(0.35, 0.35), "scale_curve": [[0.0, 1.0], [1.0, 0.5]],
			"ramp": [[0.0, Color(1, 1, 1, 0.9)], [1.0, Color(1, 1, 1, 0.0)]]})
		kc.emitting = false
		add_child(kc)
		kick[key] = kc
	trail = Fx.make_particles({"amount": 30, "lifetime": 0.35, "dir": Vector3(0, 0, 1), "spread": 5.0, "vmin": 0.5,
		"vmax": 1.0, "gravity": Vector3.ZERO, "tex": Fx.tex_soft, "size": Vector2(0.9, 0.9),
		"scale_curve": [[0.0, 1.0], [1.0, 0.1]],
		"ramp": [[0.0, Color(1.0, 0.8, 0.3, 0.6)], [1.0, Color(1.0, 0.3, 0.1, 0.0)]]})
	trail.emitting = false
	add_child(trail)
	scrape = Fx.make_particles({"amount": 50, "lifetime": 0.35, "dir": Vector3(0, 1, 1), "spread": 50.0, "vmin": 4.0,
		"vmax": 9.0, "gravity": Vector3(0, -20, 0), "tex": Fx.tex_spark, "size": Vector2(0.05, 0.24), "align": true,
		"radius": 0.15, "emission": 2.5,
		"ramp": [[0.0, Color(1, 1, 0.8, 1)], [0.5, Color(1, 0.6, 0.15, 1)], [1.0, Color(1, 0.3, 0.05, 0)]]})
	scrape.emitting = false
	add_child(scrape)
	_rebind_exhausts()


func _rebind_exhausts() -> void:
	for f in flames:
		f.queue_free()
	for c in flame_cones:
		c.queue_free()
	for p in puffs:
		p.queue_free()
	flames.clear()
	flame_cones.clear()
	puffs.clear()
	for ex in model.exhausts:
		var f := Fx.make_particles({"amount": 36, "lifetime": 0.22, "local": true, "dir": Vector3(0, 1, 0), "spread": 8.0,
			"vmin": 5.0, "vmax": 8.0, "gravity": Vector3.ZERO, "tex": Fx.tex_soft, "size": Vector2(0.32, 0.32),
			"scale_curve": [[0.0, 1.0], [1.0, 0.25]],
			"ramp": [[0.0, Color(1.0, 1.0, 0.85, 1)], [0.25, Color(1.0, 0.75, 0.2, 1)], [0.7, Color(1.0, 0.3, 0.05, 0.8)], [1.0, Color(0.6, 0.1, 0.05, 0)]]})
		f.emitting = false
		ex.add_child(f)
		flames.append(f)
		# glowing cone for the hot core of the flame
		var cone := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.0
		cm.bottom_radius = 0.075
		cm.height = 0.55
		var mat := StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = Color(1.0, 0.75, 0.3, 0.85)
		mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
		cm.material = mat
		cone.mesh = cm
		cone.position = Vector3(0, 0.3, 0)
		cone.visible = false
		cone.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		ex.add_child(cone)
		flame_cones.append(cone)
		var pf := Fx.make_particles({"amount": 6, "lifetime": 0.9, "dir": Vector3(0, 1, 0), "spread": 10.0,
			"vmin": 0.6, "vmax": 1.2, "gravity": Vector3(0, 1.0, 0), "damp": 1.0, "tex": Fx.tex_puff, "blend": "mix",
			"size": Vector2(0.22, 0.22), "scale_curve": [[0.0, 0.5], [1.0, 1.8]],
			"ramp": [[0.0, Color(0.6, 0.6, 0.62, 0.45)], [1.0, Color(0.6, 0.6, 0.62, 0)]]})
		ex.add_child(pf)
		puffs.append(pf)


# ---------------------------------------------------------------- signals

func _on_hop() -> void:
	_bounce_v += 1.6
	_squash_v += 5.5
	if kart.is_player:
		Audio.play("hop", -4.0, randf_range(0.95, 1.08))
	kart.driver.fire("hop")


func _on_land(strength: float) -> void:
	var s := clampf(strength / 10.0, 0.15, 1.0)
	_bounce_v -= 2.2 * s
	_squash_v -= 7.0 * s
	if strength > 5.0:
		Fx.burst("dust", kart.global_position, Vector3.UP, SURFACE_DUST.get(kart.surface, Color.WHITE), 0.8 + s)
		kart.driver.fire("land")
		if kart.is_player:
			Juice.shake(0.12 + 0.25 * s)
			Juice.rumble(0.3 * s, 0.6 * s, 0.15)
			Audio.play("land_big" if strength > 12.0 else "land", -2.0)
	elif kart.is_player and strength > 2.5:
		Audio.play("land", -8.0, 1.1)


func _on_boost(kind: String, _d: float) -> void:
	_squash_v += 3.0
	_flash = maxf(_flash, 0.45)
	_flash_color = Color(1.0, 0.7, 0.25)
	_pitch -= 0.06
	if kind != "trick" and kind != "mini1":
		kart.driver.fire("boost")
	if kart.is_player:
		Juice.rumble(0.4, 0.2, 0.25)
		match kind:
			"pad": Audio.play("boost_pad", -1.0)
			"rocket": Audio.play("rocket_start", 0.0)
			"item": Audio.play("miniturbo", 0.0, 0.9)
			_: Audio.play("miniturbo", -2.0, 1.0 + 0.06 * int(kind.substr(4, 1) if kind.begins_with("mini") else "0"))
	for c in flame_cones:
		c.scale = Vector3(1.6, 1.8, 1.6)


func _on_bump(strength: float, point: Vector3, normal: Vector3, other: Node) -> void:
	var s := clampf(strength / 18.0, 0.1, 1.0)
	_roll += normal.dot(kart.global_basis.x) * 0.12 * s
	_squash_v -= 3.0 * s
	Fx.burst("sparks", point, normal, Color.WHITE, 0.6 + s)
	if other == null:
		Fx.burst("stars", point + Vector3.UP * 0.5, normal, Color.WHITE, 0.5 + s * 0.6)
	_flash = maxf(_flash, 0.5 * s)
	_flash_color = Color.WHITE
	var snd := "bump_kart" if other else "bump_wall"
	if kart.is_player or (other != null and (other as Kart).is_player):
		Audio.play(snd, -2.0 + s * 3.0, randf_range(0.9, 1.1))
		Juice.shake(0.15 + 0.35 * s)
		Juice.rumble(0.5 * s, 0.8 * s, 0.18)
		if strength > 14.0:
			Juice.hitstop(0.045, 0.1)
	else:
		Audio.play_at(snd, point, -4.0, randf_range(0.9, 1.1))


func _on_spin(kind: String) -> void:
	_flash = 1.0
	_flash_color = Color(1.0, 0.95, 0.6)
	_bounce_v += 2.5
	Fx.burst("stars", kart.global_position + Vector3.UP * 1.2, Vector3.UP, Color.WHITE, 1.2)
	kart.driver.fire("hit")
	if kart.is_player:
		Audio.play("spin_out", 0.0)
		Audio.play("voice_ouch", -2.0, randf_range(0.95, 1.1), "Voice")
		Juice.shake(0.45)
		Juice.hitstop(0.08, 0.05)
		Juice.rumble(0.8, 1.0, 0.35)


func _on_tier(tier: int) -> void:
	_tier = tier
	if tier > 0:
		for key in sparks:
			Fx.burst("ring", kart.model.wheel_contact(key) + Vector3.UP * 0.2, Vector3.UP, TIER_COLORS[tier], 0.35)
		if kart.is_player:
			Audio.play("drift_tier%d" % tier, -3.0)
			Juice.rumble(0.2 * tier, 0.0, 0.08)


func _on_trick(kind: String) -> void:
	_squash_v += 4.0
	kart.driver.fire("trick", "trick_" + kind)
	Fx.burst("stars", kart.global_position + Vector3.UP, Vector3.UP, Color.WHITE, 0.8)
	if kart.is_player:
		Audio.play("trick", 0.0, randf_range(0.95, 1.1))
		Audio.play(["voice_yahoo", "voice_woohoo"][randi() % 2], -1.0, randf_range(0.95, 1.08), "Voice")


func _on_respawn_start() -> void:
	Fx.burst("splash", kart.global_position, Vector3.UP, Color.WHITE, 1.2)
	if kart.is_player:
		Audio.play("splash", 0.0)
	var tw := create_tween()
	tw.tween_property(model, "scale", Vector3(1.2, 0.2, 1.2), 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_IN)


func _on_respawned() -> void:
	model.scale = Vector3(0.3, 1.8, 0.3)
	var tw := create_tween()
	tw.tween_property(model, "scale", Vector3.ONE, 0.5).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
	Fx.burst("poof", kart.global_position + Vector3.UP * 0.6, Vector3.UP)
	if kart.is_player:
		Audio.play("respawn", -2.0)


func _on_rocket(result: int) -> void:
	if result < 0:
		for p in puffs:
			p.amount_ratio = 1.0
		Fx.burst("poof", kart.global_position + Vector3(0, 0.5, 0.8), Vector3.UP, Color(0.3, 0.3, 0.3), 0.8)
		if kart.is_player:
			Audio.play("burnout", 0.0)


# ---------------------------------------------------------------- per frame

func _process(dt: float) -> void:
	if kart == null or dt <= 0.0:
		return
	_t += dt
	var sp := kart.speed_ratio()
	# springs (semi-implicit Euler, critically-damped-ish)
	_bounce_v += (-260.0 * _bounce - 16.0 * _bounce_v) * dt
	_bounce += _bounce_v * dt
	_bounce = clampf(_bounce, -0.12, 0.2)
	_squash_v += (-300.0 * _squash - 13.0 * _squash_v) * dt
	_squash += _squash_v * dt * 0.1
	_squash = clampf(_squash, -0.22, 0.22)
	var drift_lean := -kart.drift_dir * 0.1 if kart.drifting else 0.0
	var roll_t := kart.steer_smooth * sp * 0.07 + drift_lean
	_roll = lerpf(_roll, roll_t, 1.0 - exp(-dt * 7.0))
	var pitch_t := kart.accel_signal * 0.035 * clampf(1.0 - sp, 0.3, 1.0)
	if not kart.grounded:
		pitch_t = clampf(-kart.vertical * 0.012, -0.18, 0.18)
	_pitch = lerpf(_pitch, pitch_t, 1.0 - exp(-dt * 6.0))
	var idle := 1.0 - clampf(sp * 3.0, 0.0, 1.0)
	var jit := Vector3(randf_range(-1, 1) * 0.0015, randf_range(-1, 1) * (0.004 * idle + 0.0015), 0.0)
	if kart.locked:
		jit *= 1.0 + kart.controls.throttle * 2.5
	var sq := Vector2(1.0 - _squash * 0.5, 1.0 + _squash)
	model.set_body_pose(_roll, _pitch, _bounce, sq, jit)
	# wheels
	var steer_vis := kart.steer_smooth * 0.42
	if kart.drifting:
		steer_vis = -kart.drift_dir * 0.28 + kart.controls.steer * 0.12
	_steer_vis = lerpf(_steer_vis, steer_vis, 1.0 - exp(-dt * 12.0))
	model.set_steer(-_steer_vis, kart.steer_smooth * 0.95 if not kart.drifting else kart.drift_dir * 1.2)
	var dist := kart.speed * dt
	var bumps := {}
	for key in ["fl", "fr", "rl", "rr"]:
		bumps[key] = sin(_t * 23.0 + key.hash() * 0.1) * 0.006 * sp * (2.5 if kart.is_offroad() else 1.0)
	model.roll_wheels(dist, bumps)
	model.rotation.y = kart.visual_yaw
	# flash decay
	_flash = move_toward(_flash, 0.0, dt * 3.0)
	model.set_flash(_flash, _flash_color)
	kart.driver.flash(_flash * 0.8)
	model.set_ghost(0.45 if kart.invuln > 0.0 and fmod(_t, 0.16) < 0.08 and kart.spin_time <= 0.0 else 0.0)
	_update_emitters(dt, sp)
	if kart.is_player and kart.boost_time > 0.0:
		Juice.trauma = maxf(Juice.trauma, 0.14)   # turbo rumble in the camera
	_update_driver(dt)


func _update_emitters(dt: float, sp: float) -> void:
	var drifting_ground := kart.drifting and kart.grounded
	var col: Color = TIER_COLORS[_tier]
	for key in ["rl", "rr"]:
		var pos := model.wheel_contact(key)
		var s: GPUParticles3D = sparks[key]
		s.global_position = pos
		s.global_basis = kart.global_basis
		s.emitting = drifting_ground and _tier > 0
		if s.emitting:
			var pm := s.process_material as ParticleProcessMaterial
			pm.color = col * 1.6
			s.amount_ratio = 0.4 + 0.2 * _tier
		var g: MeshInstance3D = glows[key]
		g.visible = drifting_ground and _tier > 0
		if g.visible:
			g.global_position = pos + Vector3.UP * 0.15
			var pulse := 0.8 + 0.3 * sin(_t * 40.0)
			g.scale = Vector3.ONE * (0.55 + 0.25 * _tier) * pulse
			((g.mesh as QuadMesh).material as StandardMaterial3D).albedo_color = Color(col.r, col.g, col.b, 0.85)
		var sm: GPUParticles3D = smoke[key]
		sm.global_position = pos + Vector3.UP * 0.1
		var dusty := kart.is_offroad() and absf(kart.speed) > 6.0
		var braking := kart.grounded and kart.controls.brake > 0.6 and kart.speed > 9.0
		sm.emitting = kart.grounded and (drifting_ground or braking or kart.spin_time > 0.0 or (dusty and kart.surface == "sand"))
		sm.amount_ratio = 1.0 if (kart.drifting and _tier > 0) or kart.spin_time > 0.0 else 0.6
		var surf_col: Color = SURFACE_DUST.get(kart.surface, Color.WHITE)
		(sm.process_material as ParticleProcessMaterial).color = surf_col
		var kc: GPUParticles3D = kick[key]
		kc.global_position = pos
		kc.global_basis = kart.global_basis
		kc.emitting = dusty
		(kc.process_material as ParticleProcessMaterial).color = surf_col
	_skids(drifting_ground)
	var scraping := kart.is_on_wall() and absf(kart.speed) > 8.0
	scrape.emitting = scraping
	if scraping:
		var wn := kart.get_wall_normal()
		scrape.global_position = kart.global_position - wn * 0.75 + Vector3.UP * 0.35
		scrape.global_basis = Basis.looking_at(-kart.forward(), Vector3.UP)
		if kart.is_player:
			Juice.shake(0.02)
			Juice.rumble(0.25, 0.1, 0.05)
	# boost flames
	var boosting := kart.boost_time > 0.0
	for i in flames.size():
		flames[i].emitting = boosting
		var cone := flame_cones[i]
		cone.visible = boosting
		if boosting:
			var fl := 0.8 + 0.35 * sin(_t * 55.0 + i) + randf() * 0.15
			cone.scale = cone.scale.lerp(Vector3(1.0, fl * (1.2 if kart.boost_kind.begins_with("mini3") else 1.0), 1.0), 1.0 - exp(-dt * 10.0))
		puffs[i].amount_ratio = (1.0 - sp) * 0.9 + 0.1 if not boosting else 0.0
	trail.emitting = boosting and sp > 0.6
	if trail.emitting:
		trail.global_position = kart.global_position + kart.global_basis.z * 1.2 + Vector3.UP * 0.4


const SKID_COLORS := {"road": Color(0.06, 0.06, 0.07, 0.6), "wood": Color(0.12, 0.08, 0.05, 0.45),
	"sand": Color(0.5, 0.38, 0.24, 0.6), "grass": Color(0.2, 0.15, 0.08, 0.5)}


func _skids(drifting_ground: bool) -> void:
	var sk := SkidMarks.instance
	if sk == null:
		return
	var base := kart.get_instance_id() * 4
	var braking := kart.controls.brake > 0.6 and kart.speed > 9.0
	var offroad := kart.is_offroad() and absf(kart.speed) > 3.0
	var rear := kart.grounded and (drifting_ground or braking or kart.spin_time > 0.0 or offroad or _bounce < -0.05)
	var front := kart.grounded and (offroad or kart.spin_time > 0.0)
	var col: Color = SKID_COLORS.get(kart.surface, SKID_COLORS.road)
	if offroad and not drifting_ground:
		col.a *= 0.6
	var keys := ["rl", "rr", "fl", "fr"]
	for i in 4:
		var key: String = keys[i]
		var on := rear if i < 2 else front
		if on:
			var w: Dictionary = model.wheels.get(key, {})
			var width := 0.22 if w.is_empty() else 0.2 + float(w.radius) * 0.3
			sk.mark(base + i, model.wheel_contact(key), kart.ground_normal, kart.global_basis.x, width, col)
		else:
			sk.lift(base + i)


func _update_driver(dt: float) -> void:
	var d := kart.driver
	if d == null:
		return
	d.set_drive(kart.steer_smooth, 1.0 if kart.drifting else 0.0, float(kart.drift_dir), 1.0 if kart.controls.look_back else 0.0, dt)
	var yaw := -kart.steer_smooth * 0.35
	if kart.race and kart.race.has_method("curvature_ahead"):
		yaw = -kart.race.curvature_ahead(kart, 14.0) * 9.0 + yaw * 0.4
	d.set_look(yaw, -0.05 if kart.boost_time > 0.0 else 0.0)
	d.set_wind(-kart.velocity)
