extends Node
## Screenshot harness for art review (needs a real renderer, e.g. xvfb-run):
##   xvfb-run -a godot --path . res://tools/tests/shot.tscn -- --t=6 --shots=3 --out=/tmp/race
## Starts a race in attract mode (player on autopilot), skips the intro and
## saves frames. --cam=orbit|chase ; --kart=N follows another kart.

var out := "user://shot"
var t := 6.0
var shots := 3
var every := 2.0
var race: RaceManager
var _elapsed := 0.0
var _taken := 0
var _next := 0.0
var cam_mode := "chase"
var follow := -1
var scale := 1.0
var warp := -1.0
var _warped := false


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		match kv[0]:
			"t": t = float(kv[1])
			"shots": shots = int(kv[1])
			"every": every = float(kv[1])
			"out": out = kv[1]
			"cam": cam_mode = kv[1]
			"kart": follow = int(kv[1])
			"scale": scale = float(kv[1])
			"warp": warp = float(kv[1])
			"nodecor": pass
	Engine.time_scale = scale
	var ps := load("res://scenes/race.tscn") as PackedScene
	race = ps.instantiate()
	race.autopilot_player = true
	race.skip_intro = true
	race.with_decor = not ("--nodecor" in OS.get_cmdline_user_args())
	get_tree().root.add_child.call_deferred(race)
	_next = t


func _process(dt: float) -> void:
	_elapsed += dt / maxf(Engine.time_scale, 0.001)
	if race and race.is_inside_tree() and follow >= 0 and race.camera and race.karts.size() > follow:
		if race.camera.target != race.karts[follow]:
			race.camera.follow(race.karts[follow])
	if warp >= 0.0 and not _warped and race and race.is_inside_tree() and race.state == "race":
		_warped = true
		var k := race.player
		k.global_transform = race.track.transform_at(race.track.data.start_s + warp, 0.0, 0.6)
		k.speed = 26.0
		race.progress[k].hint = race.track.locate(k.global_position).index
		race.camera.follow(k, true)
		_next = _elapsed + t
	if warp >= 0.0 and not _warped:
		return
	if _elapsed >= _next:
		var img := get_viewport().get_texture().get_image()
		var p := "%s_%d.png" % [out, _taken]
		img.save_png(p)
		print("saved ", p, " race_time=", race.race_time if race else 0.0)
		if race:
			for k in race.karts:
				var pr: Dictionary = race.progress[k]
				print("  ", k.racer_name, " lap=", pr.lap, " r=", snappedf(pr.r, 0.1), " pos=", pr.position, " v=", snappedf(k.speed, 0.1), " surf=", k.surface, " g=", k.grounded)
		_taken += 1
		_next += every
		if _taken >= shots:
			get_tree().quit()
