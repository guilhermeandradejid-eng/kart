extends Node
## Audio manager. Streams are looked up by short name in assets/audio/{sfx,music}
## (missing files are tolerated so the game runs while audio is regenerated).
## Buses: Music, SFX (with a tunnel reverb that tracks can toggle), Voice.

const SFX_DIR := "res://assets/audio/sfx/"
const MUSIC_DIR := "res://assets/audio/music/"
const LOOPING := ["engine_idle", "engine_mid", "engine_high", "drift_skid", "wind_loop", "boost_loop",
	"item_roulette", "bomb_fuse", "crowd_loop", "waves_loop", "jungle_loop"]

var _cache := {}
var _pool: Array[AudioStreamPlayer] = []
var _music_a: AudioStreamPlayer
var _music_b: AudioStreamPlayer
var _music_name := ""
var _reverb_idx := -1


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_ensure_bus("Music", "Master")
	_ensure_bus("SFX", "Master")
	_ensure_bus("Voice", "SFX")
	var sfx := AudioServer.get_bus_index("SFX")
	if AudioServer.get_bus_effect_count(sfx) == 0:
		var rv := AudioEffectReverb.new()
		rv.room_size = 0.55
		rv.damping = 0.35
		rv.wet = 0.22
		rv.dry = 1.0
		AudioServer.add_bus_effect(sfx, rv)
		var lim := AudioEffectHardLimiter.new()
		AudioServer.add_bus_effect(sfx, lim)
	_reverb_idx = 0
	AudioServer.set_bus_effect_enabled(sfx, _reverb_idx, false)
	for i in 24:
		var p := AudioStreamPlayer.new()
		p.bus = "SFX"
		add_child(p)
		_pool.append(p)
	_music_a = AudioStreamPlayer.new()
	_music_b = AudioStreamPlayer.new()
	for m in [_music_a, _music_b]:
		m.bus = "Music"
		add_child(m)


func _ensure_bus(bus_name: String, send: String) -> void:
	if AudioServer.get_bus_index(bus_name) >= 0:
		return
	AudioServer.add_bus()
	var idx := AudioServer.bus_count - 1
	AudioServer.set_bus_name(idx, bus_name)
	AudioServer.set_bus_send(idx, send)


func stream(sound_name: String, dir := SFX_DIR) -> AudioStream:
	var key := dir + sound_name
	if _cache.has(key):
		return _cache[key]
	var s: AudioStream = null
	for ext in [".ogg", ".wav"]:
		var path: String = key + ext
		if ResourceLoader.exists(path):
			s = load(path)
			break
	if s is AudioStreamOggVorbis:
		(s as AudioStreamOggVorbis).loop = sound_name in LOOPING or dir == MUSIC_DIR and not sound_name.begins_with("jingle")
	elif s is AudioStreamWAV and sound_name in LOOPING:
		(s as AudioStreamWAV).loop_mode = AudioStreamWAV.LOOP_FORWARD
		(s as AudioStreamWAV).loop_end = int((s as AudioStreamWAV).get_length() * (s as AudioStreamWAV).mix_rate)
	_cache[key] = s
	return s


## Non-positional one-shot (UI, player-only feedback).
func play(sound_name: String, volume_db := 0.0, pitch := 1.0, bus := "SFX") -> AudioStreamPlayer:
	var s := stream(sound_name)
	if s == null:
		return null
	var p: AudioStreamPlayer = null
	for cand in _pool:
		if not cand.playing:
			p = cand
			break
	if p == null:
		p = _pool[0]
	p.stream = s
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.bus = bus
	p.play()
	return p


## Positional one-shot that frees itself.
func play_at(sound_name: String, pos: Vector3, volume_db := 0.0, pitch := 1.0, parent: Node = null) -> void:
	var s := stream(sound_name)
	if s == null:
		return
	var p := AudioStreamPlayer3D.new()
	p.stream = s
	p.volume_db = volume_db
	p.pitch_scale = pitch
	p.bus = "SFX"
	p.unit_size = 12.0
	p.max_distance = 140.0
	p.attenuation_filter_cutoff_hz = 9000.0
	var host := parent if parent else get_tree().current_scene
	if host == null:
		return
	host.add_child(p)
	p.global_position = pos
	p.finished.connect(p.queue_free)
	p.play()


## Looping positional player owned by `parent` (engines, skids).
func make_loop(sound_name: String, parent: Node3D, volume_db := 0.0) -> AudioStreamPlayer3D:
	var p := AudioStreamPlayer3D.new()
	p.stream = stream(sound_name)
	p.volume_db = volume_db
	p.bus = "SFX"
	p.unit_size = 10.0
	p.max_distance = 120.0
	parent.add_child(p)
	if p.stream:
		p.play()
	return p


func music(track: String, fade := 1.0, pitch := 1.0) -> void:
	if track == _music_name:
		_music_a.pitch_scale = pitch
		return
	_music_name = track
	var s := stream(track, MUSIC_DIR)
	var old := _music_a
	_music_a = _music_b
	_music_b = old
	if old.playing:
		var tw := create_tween()
		tw.tween_property(old, "volume_db", -40.0, fade)
		tw.tween_callback(old.stop)
	if s:
		_music_a.stream = s
		_music_a.volume_db = -30.0
		_music_a.pitch_scale = pitch
		_music_a.play()
		create_tween().tween_property(_music_a, "volume_db", 0.0, fade * 0.8)


func music_pitch(pitch: float, time := 0.6) -> void:
	create_tween().tween_property(_music_a, "pitch_scale", pitch, time)


func stop_music(fade := 0.8) -> void:
	_music_name = ""
	create_tween().tween_property(_music_a, "volume_db", -40.0, fade)


func set_tunnel_reverb(on: bool) -> void:
	AudioServer.set_bus_effect_enabled(AudioServer.get_bus_index("SFX"), _reverb_idx, on)
