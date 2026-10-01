extends Node
## Headless race simulation for tuning/regression:
##   godot --headless --path . res://tools/tests/sim.tscn -- --t=60 --every=1 [--kart=5]
var t := 30.0
var every := 1.0
var race: RaceManager
var _el := 0.0
var _next := 0.0
var watch := -1


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		match kv[0]:
			"t": t = float(kv[1])
			"every": every = float(kv[1])
			"kart": watch = int(kv[1])
	race = (load("res://scenes/race.tscn") as PackedScene).instantiate()
	race.autopilot_player = true
	race.skip_intro = true
	race.with_decor = false
	get_tree().root.add_child.call_deferred(race)


func _physics_process(dt: float) -> void:
	_el += dt
	if race == null or not race.is_inside_tree() or race.state != "race" and race.state != "finished":
		return
	if race.race_time >= _next:
		_next += every
		var line := "t=%5.1f " % race.race_time
		for i in race.karts.size():
			if watch >= 0 and i != watch:
				continue
			var k: Kart = race.karts[i]
			var pr: Dictionary = race.progress[k]
			var loc := race.track.locate(k.global_position, pr.hint)
			line += "| %s L%d r%.0f lat%+.1f/%.0f v%.0f st%+.1f %s%s%s " % [k.racer_name.substr(0, 3), pr.lap, pr.r, loc.lateral,
				loc.half_width, k.speed, k.controls.steer, k.surface.substr(0, 1), "D" if k.drifting else "", "A" if not k.grounded else ""]
		print(line)
	if race.race_time >= t:
		get_tree().quit()
