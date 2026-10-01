class_name KartAudio
extends Node3D
## Engine made of three looping layers (idle / mid / high) crossfaded and
## pitch-shifted by a smoothed RPM, plus skid, wind and boost loops.
## Rival karts are quieter and rely on 3D attenuation.

var kart: Kart
var idle: AudioStreamPlayer3D
var mid: AudioStreamPlayer3D
var high: AudioStreamPlayer3D
var skid: AudioStreamPlayer3D
var wind: AudioStreamPlayer3D
var boost: AudioStreamPlayer3D
var rpm := 0.0
var _base := 0.0
var _pitch_mul := 1.0


func setup(k: Kart) -> void:
	kart = k
	_base = 0.0 if k.is_player else -7.0
	_pitch_mul = KartParts.part("engine", k.config.engine).get("pitch", 1.0) * randf_range(0.97, 1.03)
	idle = Audio.make_loop("engine_idle", self, -80)
	mid = Audio.make_loop("engine_mid", self, -80)
	high = Audio.make_loop("engine_high", self, -80)
	skid = Audio.make_loop("drift_skid", self, -80)
	if k.is_player:
		wind = Audio.make_loop("wind_loop", self, -80)
	boost = Audio.make_loop("boost_loop", self, -80)
	for p in [idle, mid, high, skid, wind, boost]:
		if p:
			p.stream_paused = false
	kart.hopped.connect(func(): pass)


func _process(dt: float) -> void:
	if kart == null:
		return
	var target := clampf(absf(kart.speed) / (kart.tuning.max_speed * 1.05), 0.0, 1.35)
	if kart.locked:
		target = kart.controls.throttle * 0.85 + sin(Time.get_ticks_msec() * 0.03) * 0.03 * kart.controls.throttle
	if not kart.grounded:
		target += 0.15  # wheels spin free in the air
	if kart.boost_time > 0.0:
		target += 0.12
	rpm = lerpf(rpm, target, 1.0 - exp(-dt * (8.0 if target > rpm else 4.0)))
	var p := (0.75 + rpm * 0.75) * _pitch_mul
	_layer(idle, 1.0 - smoothstep(0.08, 0.4, rpm), p * 1.0)
	_layer(mid, smoothstep(0.1, 0.45, rpm) * (1.0 - smoothstep(0.7, 1.0, rpm)), p * 0.85)
	_layer(high, smoothstep(0.55, 0.95, rpm), p * 0.72)
	var drifting := kart.drifting and kart.grounded
	_layer(skid, 0.7 if drifting else 0.0, 0.9 + 0.08 * kart.drift_tier_level, 8.0)
	if wind:
		_layer(wind, smoothstep(0.35, 1.2, kart.speed_ratio()) * 0.8, 0.8 + kart.speed_ratio() * 0.5, 3.0)
	_layer(boost, 0.8 if kart.boost_time > 0.0 else 0.0, 1.0, 10.0)


func _layer(pl: AudioStreamPlayer3D, vol: float, pitch: float, speed := 6.0) -> void:
	if pl == null:
		return
	var db := linear_to_db(maxf(vol, 0.0001)) + _base
	pl.volume_db = lerpf(pl.volume_db, db, 1.0 - exp(-get_process_delta_time() * speed))
	pl.pitch_scale = clampf(pitch, 0.3, 3.0)
