extends Node
## Global game state: settings, the player's kart build, race setup and
## scene transitions (with a juicy iris/fade wipe).

signal settings_changed

const SAVE_PATH := "user://turbo_turma.cfg"
const DIFFICULTIES := {
	"facil": {"label": "50cc", "speed": 0.86, "ai_skill": 0.55},
	"medio": {"label": "100cc", "speed": 0.95, "ai_skill": 0.75},
	"dificil": {"label": "150cc", "speed": 1.04, "ai_skill": 0.95},
}

var player_config: KartConfig
var difficulty := "medio"
var laps := 3
var track_id := "coconut_bay"
var settings := {
	"music_volume": 0.7, "sfx_volume": 0.85, "fullscreen": false, "quality": "high",
	"camera_shake": 1.0, "rumble": true, "show_fps": false,
}
var last_results: Array = []

var _fade: ColorRect
var _fade_layer: CanvasLayer


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	player_config = KartConfig.new()
	_load()
	_fade_layer = CanvasLayer.new()
	_fade_layer.layer = 100
	add_child(_fade_layer)
	_fade = ColorRect.new()
	_fade.color = Color(0.03, 0.02, 0.06, 0.0)
	_fade.set_anchors_preset(Control.PRESET_FULL_RECT)
	_fade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/ui/wipe.gdshader")
	_fade.material = mat
	_fade_layer.add_child(_fade)
	apply_settings()


func difficulty_info() -> Dictionary:
	return DIFFICULTIES[difficulty]


func goto_scene(path: String, duration := 0.45) -> void:
	get_tree().paused = false
	var mat := _fade.material as ShaderMaterial
	var tw := create_tween().set_pause_mode(Tween.TWEEN_PAUSE_PROCESS)
	_fade.color.a = 1.0
	tw.tween_method(func(v): mat.set_shader_parameter("progress", v), 0.0, 1.0, duration).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN)
	tw.tween_callback(func(): get_tree().change_scene_to_file(path))
	tw.tween_interval(0.08)
	tw.tween_method(func(v): mat.set_shader_parameter("progress", v), 1.0, 0.0, duration).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)


func apply_settings() -> void:
	var mode := DisplayServer.WINDOW_MODE_FULLSCREEN if settings.fullscreen else DisplayServer.WINDOW_MODE_WINDOWED
	if DisplayServer.get_name() != "headless" and DisplayServer.window_get_mode() != mode:
		DisplayServer.window_set_mode(mode)
	var master_bus := AudioServer.get_bus_index("Music")
	if master_bus >= 0:
		AudioServer.set_bus_volume_db(master_bus, linear_to_db(maxf(settings.music_volume, 0.0001)))
	var sfx_bus := AudioServer.get_bus_index("SFX")
	if sfx_bus >= 0:
		AudioServer.set_bus_volume_db(sfx_bus, linear_to_db(maxf(settings.sfx_volume, 0.0001)))
	settings_changed.emit()


func save() -> void:
	var cfg := ConfigFile.new()
	for k in settings:
		cfg.set_value("settings", k, settings[k])
	cfg.set_value("race", "difficulty", difficulty)
	cfg.set_value("race", "laps", laps)
	cfg.set_value("kart", "config", player_config.to_dict())
	cfg.save(SAVE_PATH)


func _load() -> void:
	var cfg := ConfigFile.new()
	if cfg.load(SAVE_PATH) != OK:
		return
	for k in settings:
		settings[k] = cfg.get_value("settings", k, settings[k])
	difficulty = cfg.get_value("race", "difficulty", difficulty)
	laps = cfg.get_value("race", "laps", laps)
	var d: Dictionary = cfg.get_value("kart", "config", {})
	if not d.is_empty():
		player_config = KartConfig.from_dict(d)
