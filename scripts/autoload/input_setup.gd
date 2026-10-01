extends Node
## Registers every input action in code so keyboard + gamepad work out of the box
## and the project stays text-diffable. (Remappable later through InputMap.)

const ACTIONS := {
	"accelerate": [KEY_W, KEY_UP, [JOY_BUTTON_A], [JOY_AXIS_TRIGGER_RIGHT, 1.0]],
	"brake": [KEY_S, KEY_DOWN, [JOY_BUTTON_B], [JOY_AXIS_TRIGGER_LEFT, 1.0]],
	"steer_left": [KEY_A, KEY_LEFT, [JOY_BUTTON_DPAD_LEFT], [JOY_AXIS_LEFT_X, -1.0]],
	"steer_right": [KEY_D, KEY_RIGHT, [JOY_BUTTON_DPAD_RIGHT], [JOY_AXIS_LEFT_X, 1.0]],
	"drift": [KEY_SPACE, KEY_SHIFT, [JOY_BUTTON_RIGHT_SHOULDER], [JOY_BUTTON_X]],
	"item": [KEY_E, KEY_CTRL, [JOY_BUTTON_LEFT_SHOULDER]],
	"look_back": [KEY_Q, [JOY_BUTTON_Y]],
	"pause": [KEY_ESCAPE, KEY_P, [JOY_BUTTON_START]],
	"ui_accept_alt": [KEY_ENTER, KEY_SPACE, [JOY_BUTTON_A]],
	"camera_toggle": [KEY_C, [JOY_BUTTON_BACK]],
}


func _ready() -> void:
	for action in ACTIONS:
		if not InputMap.has_action(action):
			InputMap.add_action(action, 0.2)
		for binding in ACTIONS[action]:
			var ev: InputEvent
			if binding is int:
				var k := InputEventKey.new()
				k.physical_keycode = binding
				ev = k
			elif binding.size() == 1:
				var b := InputEventJoypadButton.new()
				b.button_index = binding[0]
				ev = b
			else:
				var m := InputEventJoypadMotion.new()
				m.axis = binding[0]
				m.axis_value = binding[1]
				ev = m
			InputMap.action_add_event(action, ev)
