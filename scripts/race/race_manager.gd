class_name RaceManager
extends Node3D
## Runs a race: builds the track, 8 karts (1 player + 7 rivals), the camera and
## HUD, then drives intro -> countdown -> race -> finish -> results.

signal countdown_tick(n: int)        # 3, 2, 1, 0 (= GO)
signal lap_changed(kart: Kart, lap: int)
signal final_lap
signal positions_changed
signal race_finished(results: Array)
signal message(text: String, style: String)
signal wrong_way(on: bool)

const RIVALS := ["Prata", "Chocolate", "Dourado", "Anil", "Amora", "Neve", "Musgo"]
const ITEM_TABLE := {
	"front": {"banana": 0.6, "coconut": 0.28, "pepper": 0.12},
	"middle": {"banana": 0.3, "coconut": 0.38, "pepper": 0.32},
	"back": {"banana": 0.1, "coconut": 0.35, "pepper": 0.55},
}

@export var autopilot_player := false    # tests / attract mode
@export var skip_intro := false
@export var with_decor := true
@export var num_karts := 8

var track: Track
var camera: ChaseCamera
var hud: Node
var karts: Array[Kart] = []
var player: Kart
var progress := {}                       # kart -> Dictionary
var order: Array[Kart] = []
var laps := 3
var race_time := 0.0
var countdown_left := 99.0
var state := "loading"                   # intro, countdown, race, finished
var finish_order: Array[Kart] = []
var _rng := RandomNumberGenerator.new()
var _band_timer := 0.0
var _wrong_time := 0.0
var _wrong := false
var _final_lap_announced := false
var _in_tunnel := false
var _results_shown := false


func _ready() -> void:
	_rng.seed = Time.get_ticks_usec()
	laps = Game.laps
	track = Track.new()
	track.name = "Track"
	add_child(track)
	track.load_track(Game.track_id, with_decor)
	_spawn_karts()
	camera = ChaseCamera.new()
	camera.name = "Camera"
	add_child(camera)
	camera.follow(player)
	var hud_scene: GDScript = load("res://scripts/ui/hud.gd")
	if hud_scene:
		hud = hud_scene.new()
		hud.name = "HUD"
		add_child(hud)
		hud.bind(self)
	_ambience()
	if skip_intro:
		_start_countdown()
	else:
		_start_intro()


func _spawn_karts() -> void:
	var diff := Game.difficulty_info()
	var player_slot := mini(5, num_karts - 1)
	var ai_i := 0
	for slot in num_karts:
		var k := Kart.new()
		var is_p := slot == player_slot
		var cfg: KartConfig = Game.player_config.duplicate_config() if is_p else KartConfig.random(_rng)
		var variant := 0 if is_p else (ai_i % 7) + 1
		k.name = "Kart%d" % slot
		add_child(k)
		k.global_transform = track.grid_transform(slot)
		k.setup(cfg, is_p, variant)
		k.race = self
		k.grid_index = slot
		k.racer_name = "Guará" if is_p else RIVALS[ai_i % RIVALS.size()]
		k.speed_mult = diff.speed
		k.add_to_group("karts")
		var fx := KartFX.new()
		fx.name = "FX"
		k.add_child(fx)
		fx.setup(k)
		var au := KartAudio.new()
		au.name = "Audio"
		k.add_child(au)
		au.setup(k)
		if is_p and not autopilot_player:
			var pc := PlayerController.new()
			pc.kart = k
			k.add_child(pc)
			player = k
		else:
			var ai := AIController.new()
			ai.name = "AI"
			k.add_child(ai)
			var skill: float = clampf(diff.ai_skill + _rng.randf_range(-0.12, 0.08), 0.3, 1.0)
			if is_p:
				skill = 0.9
				player = k
			ai.setup(k, track, self, skill, _rng.randi())
			ai_i += 0 if is_p else 1
		karts.append(k)
		var loc := track.locate(k.global_position)
		progress[k] = {"lap": 0, "r": _rel(loc.s), "cp": 3, "hint": loc.index, "total": 0.0, "finished": false,
			"time": 0.0, "lap_start": 0.0, "lap_times": [], "position": slot + 1}
		k.driver.set_state("countdown")
	order = karts.duplicate()


func _rel(s: float) -> float:
	return fposmod(s - track.data.start_s, track.length)


func _ambience() -> void:
	Audio.music("music_race", 1.5)
	var w := Audio.make_loop("waves_loop", camera, -12.0)
	var c := Audio.make_loop("crowd_loop", camera, -16.0)
	if w:
		w.unit_size = 1000.0
	if c:
		c.unit_size = 1000.0


# ------------------------------------------------------------------ intro

func _start_intro() -> void:
	state = "intro"
	var st := track.transform_at(track.data.start_s, 0.0, 0.0)
	var f := -st.basis.z
	var r := st.basis.x
	var p := st.origin
	var pts := [
		[p + f * 70.0 + r * 40.0 + Vector3.UP * 45.0, p + f * 10.0],
		[p + f * 35.0 - r * 30.0 + Vector3.UP * 16.0, p - f * 10.0],
		[p + f * 8.0 + r * 12.0 + Vector3.UP * 4.0, p - f * 18.0 + Vector3.UP],
		[player.global_position - player.forward() * 5.6 + Vector3.UP * 2.15, player.global_position + Vector3.UP + player.forward() * 3.0],
	]
	camera.play_intro(pts, 5.5)
	message.emit(track.data.name, "title")
	get_tree().create_timer(5.6).timeout.connect(_start_countdown)


func _start_countdown() -> void:
	if state == "countdown" or state == "race":
		return
	state = "countdown"
	camera.mode = ChaseCamera.Mode.CHASE
	camera.follow(player, true)
	countdown_left = 3.6
	for k in karts:
		k.driver.set_state("countdown")


func _countdown_process(dt: float) -> void:
	var before := countdown_left
	countdown_left -= dt
	for k in karts:
		k.set_countdown(countdown_left)
	for n in [3, 2, 1]:
		if before > n and countdown_left <= n:
			countdown_tick.emit(n)
			Audio.play("countdown_beep", -2.0)
	if countdown_left <= 0.0:
		countdown_tick.emit(0)
		Audio.play("countdown_go", 0.0)
		Audio.play("crowd_cheer", -6.0)
		state = "race"
		race_time = 0.0
		for k in karts:
			k.release()
			k.driver.set_state("race")
			progress[k].lap_start = 0.0


# ------------------------------------------------------------------ race loop

func _physics_process(dt: float) -> void:
	match state:
		"countdown":
			_countdown_process(dt)
		"race", "finished":
			race_time += dt
			_track_progress(dt)
			_rank()
			_band(dt)
			_player_checks(dt)


func _track_progress(_dt: float) -> void:
	var L := track.length
	for k in karts:
		var p: Dictionary = progress[k]
		if p.finished:
			continue
		var loc := track.locate(k.global_position, p.hint)
		p.hint = loc.index
		var r := _rel(loc.s)
		var d: float = r - p.r
		if d < -L * 0.5:
			# crossed the line forwards
			if p.cp >= 3:
				p.lap += 1
				p.cp = 0
				if p.lap > 1:
					p.lap_times.append(race_time - p.lap_start)
				p.lap_start = race_time
				if p.lap > laps:
					_finish(k)
				else:
					lap_changed.emit(k, p.lap)
					if k == player and p.lap == laps and not _final_lap_announced:
						_final_lap_announced = true
						final_lap.emit()
						message.emit("VOLTA FINAL!", "big")
						Audio.play("final_lap", 0.0)
						Audio.music_pitch(1.08)
					elif k == player and p.lap > 1:
						Audio.play("lap", -2.0)
						message.emit("VOLTA %d" % p.lap, "lap")
		elif d > L * 0.5:
			# backwards over the line
			p.lap -= 1
			p.cp = 3
		else:
			var cps: Array = [0.25, 0.5, 0.75]
			if p.cp < 3 and r >= L * cps[p.cp] and p.r < L * cps[p.cp] + 30.0:
				p.cp += 1
		p.r = r
		p.total = (p.lap - 1) * L + r if p.lap >= 1 else r - L


func _rank() -> void:
	var prev := order.duplicate()
	order.sort_custom(func(a: Kart, b: Kart) -> bool:
		var pa: Dictionary = progress[a]
		var pb: Dictionary = progress[b]
		if pa.finished != pb.finished:
			return pa.finished
		if pa.finished:
			return finish_order.find(a) < finish_order.find(b)
		return pa.total > pb.total)
	for i in order.size():
		progress[order[i]].position = i + 1
	if prev != order:
		positions_changed.emit()


func _band(dt: float) -> void:
	_band_timer -= dt
	if _band_timer > 0.0 or player == null:
		return
	_band_timer = 0.5
	var diff := Game.difficulty_info()
	var pt: float = progress[player].total
	for k in karts:
		if k == player:
			continue
		var gap: float = progress[k].total - pt
		var f := 1.0
		if gap < -40.0:
			f = 1.0 + clampf((-gap - 40.0) / 300.0, 0.0, 0.1)
		elif gap > 60.0:
			f = 1.0 - clampf((gap - 60.0) / 400.0, 0.0, 0.07)
		k.speed_mult = diff.speed * f


func _player_checks(dt: float) -> void:
	if player == null or progress[player].finished:
		return
	var loc := track.locate(player.global_position, progress[player].hint)
	var fr := track.frame_at(loc.s)
	var backwards := player.forward().dot(fr.f) < -0.25 and player.speed > 3.0
	_wrong_time = _wrong_time + dt if backwards else maxf(_wrong_time - dt * 2.0, 0.0)
	var w := _wrong_time > 1.1
	if w != _wrong:
		_wrong = w
		wrong_way.emit(w)
		if w:
			Audio.play("wrong_way", -3.0)
	var tun := track.has_tag(loc.s, "tunnel")
	if tun != _in_tunnel:
		_in_tunnel = tun
		Audio.set_tunnel_reverb(tun)


func _finish(k: Kart) -> void:
	var p: Dictionary = progress[k]
	p.finished = true
	p.time = race_time
	finish_order.append(k)
	k.finished = true
	var place := finish_order.size()
	if k == player:
		state = "finished"
		# hand the wheel to the autopilot and celebrate
		for c in k.get_children():
			if c is PlayerController:
				(c as PlayerController).enabled = false
				c.queue_free()
		var ai := AIController.new()
		k.add_child(ai)
		ai.setup(k, track, self, 0.8, 7)
		k.driver.set_state("victory" if place <= 3 else "lose")
		Juice.slowmo(0.35, 0.9, 0.8)
		Fx.burst("confetti", k.global_position + Vector3.UP * 2.0, Vector3.UP, Color.WHITE, 1.0)
		Audio.play("finish", 0.0)
		Audio.play("crowd_cheer", -2.0)
		Audio.music("jingle_victory" if place <= 3 else "jingle_lose", 0.5)
		if place <= 3:
			Audio.play("voice_laugh", -1.0, 1.0, "Voice")
		else:
			Audio.play("voice_aww", -1.0, 1.0, "Voice")
		camera.orbit(k)
		message.emit("%dº LUGAR!" % place if place <= 3 else "FIM!", "finish")
		get_tree().create_timer(6.5).timeout.connect(_show_results)
	else:
		k.driver.set_state("victory" if place <= 3 else "lose")


func _show_results() -> void:
	if _results_shown:
		return
	_results_shown = true
	# rank everyone still racing by current order, estimate their times
	var results := []
	for k in order:
		var p: Dictionary = progress[k]
		var t: float = p.time
		if not p.finished:
			var remaining: float = laps * track.length - p.total
			t = race_time + remaining / maxf(k.tuning.max_speed * 0.8, 1.0)
		results.append({"name": k.racer_name, "time": t, "player": k == player, "config": k.config,
			"finished": p.finished, "shells": k.shells})
	results.sort_custom(func(a, b): return a.time < b.time)
	Game.last_results = results
	Audio.music("music_results", 1.0)
	race_finished.emit(results)


# ------------------------------------------------------------------ services for karts

func water_level() -> float:
	return track.water_level


func respawn_transform(k: Kart) -> Transform3D:
	var p: Dictionary = progress.get(k, {})
	var s: float = track.locate(k.last_safe.origin, p.get("hint", -1)).s
	# step back a little, clear of the gap / water
	s -= 4.0
	for i in 20:
		if track.has_tag(s, "gap") or track.has_tag(s + 6.0, "gap"):
			s -= 6.0
		else:
			break
	var lat := clampf(track.locate(k.last_safe.origin).lateral, -3.0, 3.0)
	return track.transform_at(s, lat, 0.4)


func curvature_ahead(k: Kart, dist: float) -> float:
	var p: Dictionary = progress.get(k, {})
	var s: float = track.svals[p.get("hint", 0)]
	return track.curvature_ahead(s, dist, 6.0)


func position_of(k: Kart) -> int:
	return progress[k].position if progress.has(k) else 1


func lap_of(k: Kart) -> int:
	return clampi(progress[k].lap, 1, laps) if progress.has(k) else 1


func roll_item(k: Kart) -> String:
	var pos := position_of(k)
	var key := "middle"
	if pos <= 2:
		key = "front"
	elif pos >= karts.size() - 1:
		key = "back"
	var table: Dictionary = ITEM_TABLE[key]
	var r := _rng.randf()
	for it in table:
		r -= table[it]
		if r <= 0.0:
			return it
	return "banana"


func use_item(k: Kart, it: String) -> void:
	match it:
		"pepper":
			k.boost("item", 1.7)
			Fx.burst("ring", k.global_position + Vector3.UP * 0.5, Vector3.UP, Color(1, 0.35, 0.1), 1.3)
			k.driver.fire("action", "cheer")
			if k.is_player:
				Audio.play("voice_yip", -2.0, 1.0, "Voice")
		"banana":
			var b := Banana.new()
			b.owner_kart = k
			add_child(b)
			b.global_position = _ground(k.global_position + k.global_basis.z * 2.3)
			k.driver.fire("action", "throw_back")
			Audio.play_at("banana_drop", b.global_position, -2.0)
		"coconut":
			var c := CoconutBomb.new()
			c.owner_kart = k
			c.track = track
			add_child(c)
			c.global_position = k.global_position + k.forward() * 2.0 + Vector3.UP * 1.0
			c.velocity = k.forward() * (maxf(k.speed, 10.0) + 12.0) + Vector3.UP * 4.0
			k.driver.fire("action", "throw_fwd")
			Audio.play_at("bomb_throw", c.global_position, 0.0)


func _ground(p: Vector3) -> Vector3:
	var space := get_world_3d().direct_space_state
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 3.0, p + Vector3.DOWN * 6.0, 1)
	var r := space.intersect_ray(q)
	return r.position if not r.is_empty() else p


func restart() -> void:
	Game.goto_scene("res://scenes/race.tscn")


func quit_to_menu() -> void:
	Game.goto_scene("res://scenes/main_menu.tscn")
