extends Node
## Game-feel utilities shared by every system: hit-stop, slow motion,
## screen shake (trauma model, consumed by the active ChaseCamera) and rumble.

var trauma := 0.0            # 0..1, shake = trauma^2
var _hitstop_until := 0
var _slowmo_tween: Tween


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS


func _process(delta: float) -> void:
	trauma = maxf(trauma - delta * 1.6, 0.0)
	if _hitstop_until > 0 and Time.get_ticks_msec() >= _hitstop_until:
		_hitstop_until = 0
		Engine.time_scale = 1.0


func shake(amount: float) -> void:
	trauma = clampf(trauma + amount * Game.settings.camera_shake, 0.0, 1.0)


## Freeze-frame for impact. Uses real time so it always releases.
func hitstop(duration := 0.06, scale := 0.05) -> void:
	Engine.time_scale = scale
	_hitstop_until = Time.get_ticks_msec() + int(duration * 1000.0)


func slowmo(scale := 0.3, hold := 0.6, ease_back := 0.5) -> void:
	if _slowmo_tween:
		_slowmo_tween.kill()
	Engine.time_scale = scale
	_slowmo_tween = create_tween().set_ignore_time_scale(true)
	_slowmo_tween.tween_interval(hold)
	_slowmo_tween.tween_property(Engine, "time_scale", 1.0, ease_back).set_trans(Tween.TRANS_SINE)


func rumble(weak: float, strong: float, duration: float, device := 0) -> void:
	if not Game.settings.rumble:
		return
	Input.start_joy_vibration(device, clampf(weak, 0, 1), clampf(strong, 0, 1), duration)
