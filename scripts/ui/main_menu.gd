extends Node
## Title + main menu over the sunset showroom. Bouncy logo letters, "press
## start" pulse, then menu buttons, race setup and options panels.

var showroom: Showroom
var ui: Control
var logo: Control
var press: Label
var menu: VBoxContainer
var setup_panel: PanelContainer
var options_panel: PanelContainer
var _letters: Array[Label] = []
var _t := 0.0
var _started := false


func _ready() -> void:
	showroom = Showroom.new()
	add_child(showroom)
	showroom.cam_target = Vector3(1.4, 0.75, 0)
	showroom.cam_dist = 5.2
	showroom.cam_yaw = 0.9
	var layer := CanvasLayer.new()
	add_child(layer)
	ui = Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.theme = UIKit.theme()
	layer.add_child(ui)
	_build_logo()
	press = UIKit.label("Pressione ENTER ou START", 40, true, UIKit.CREAM, 10)
	press.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	press.position = Vector2(-330, -170)
	press.size = Vector2(660, 60)
	press.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ui.add_child(press)
	menu = VBoxContainer.new()
	menu.set_anchors_preset(Control.PRESET_CENTER_LEFT)
	menu.position = Vector2(110, -40)
	menu.size = Vector2(440, 420)
	menu.add_theme_constant_override("separation", 16)
	menu.visible = false
	ui.add_child(menu)
	for pair in [["Corrida Rápida", _open_setup], ["Garagem", _garage], ["Opções", _open_options], ["Sair", _quit]]:
		menu.add_child(_button(pair[0], pair[1]))
	_build_setup()
	_build_options()
	var credit := UIKit.label("v0.1 MVP  •  Godot 4.7 + Blender", 20, false, Color(1, 1, 1, 0.6), 4)
	credit.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	credit.position = Vector2(-420, -44)
	ui.add_child(credit)
	Audio.music("music_menu", 1.2)


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.custom_minimum_size = Vector2(420, 72)
	b.pressed.connect(func(): Audio.play("ui_select", -3.0); cb.call())
	b.focus_entered.connect(func(): Audio.play("ui_move", -8.0); UIKit.punch(b, 1.06, 0.3))
	b.mouse_entered.connect(b.grab_focus)
	return b


func _build_logo() -> void:
	logo = Control.new()
	logo.set_anchors_preset(Control.PRESET_CENTER_TOP)
	logo.position = Vector2(-560, 70)
	logo.size = Vector2(1120, 260)
	ui.add_child(logo)
	var words := [["TURBO", UIKit.YELLOW, 0.0], ["TURMA", UIKit.ORANGE, 150.0]]
	var x := 0.0
	for w in words:
		x = 120.0 if w[0] == "TURBO" else 230.0
		for ch in (w[0] as String):
			var l := UIKit.label(ch, 150, true, w[1], 24)
			l.position = Vector2(x, w[2])
			logo.add_child(l)
			_letters.append(l)
			x += 132.0 if ch != "M" else 160.0
	var sub := UIKit.label("Corrida na Baía dos Coqueiros", 36, false, UIKit.CREAM, 8)
	sub.position = Vector2(330, 312)
	logo.add_child(sub)
	for i in _letters.size():
		var l := _letters[i]
		l.pivot_offset = Vector2(60, 90)
		l.scale = Vector2.ZERO
		var tw := create_tween()
		tw.tween_interval(0.25 + i * 0.06)
		tw.tween_property(l, "scale", Vector2.ONE, 0.6).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)


func _build_setup() -> void:
	setup_panel = PanelContainer.new()
	setup_panel.set_anchors_preset(Control.PRESET_CENTER_LEFT)
	setup_panel.position = Vector2(100, -170)
	setup_panel.size = Vector2(560, 470)
	setup_panel.visible = false
	ui.add_child(setup_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 18)
	setup_panel.add_child(v)
	v.add_child(UIKit.label("Corrida Rápida", 54, true, UIKit.YELLOW, 12))
	v.add_child(UIKit.label("Pista: Baía dos Coqueiros", 30))
	var diff := _option_row("Categoria", ["facil", "medio", "dificil"].map(func(d): return Game.DIFFICULTIES[d].label),
		["facil", "medio", "dificil"].find(Game.difficulty), func(i): Game.difficulty = ["facil", "medio", "dificil"][i])
	v.add_child(diff)
	var laps := _option_row("Voltas", ["1", "2", "3", "4", "5"], Game.laps - 1, func(i): Game.laps = i + 1)
	v.add_child(laps)
	var go := _button("Largar!", _start_race)
	v.add_child(go)
	v.add_child(_button("Voltar", _back))


func _option_row(title: String, opts: Array, sel: int, cb: Callable) -> HBoxContainer:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	var t := UIKit.label(title, 30)
	t.custom_minimum_size = Vector2(180, 0)
	h.add_child(t)
	var state := {"i": sel}
	var val := UIKit.label(str(opts[sel]), 34, true, UIKit.YELLOW)
	val.custom_minimum_size = Vector2(150, 0)
	val.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var left := Button.new()
	left.text = "<"
	var right := Button.new()
	right.text = ">"
	var step := func(d: int):
		state.i = posmod(state.i + d, opts.size())
		val.text = str(opts[state.i])
		UIKit.punch(val, 1.3, 0.3)
		Audio.play("ui_move", -5.0)
		cb.call(state.i)
	left.pressed.connect(step.bind(-1))
	right.pressed.connect(step.bind(1))
	h.add_child(left)
	h.add_child(val)
	h.add_child(right)
	return h


func _build_options() -> void:
	options_panel = PanelContainer.new()
	options_panel.set_anchors_preset(Control.PRESET_CENTER_LEFT)
	options_panel.position = Vector2(100, -220)
	options_panel.size = Vector2(620, 540)
	options_panel.visible = false
	ui.add_child(options_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 14)
	options_panel.add_child(v)
	v.add_child(UIKit.label("Opções", 54, true, UIKit.YELLOW, 12))
	for spec in [["Música", "music_volume"], ["Efeitos", "sfx_volume"], ["Tremor de câmera", "camera_shake"]]:
		var h := HBoxContainer.new()
		var l := UIKit.label(spec[0], 28)
		l.custom_minimum_size = Vector2(260, 0)
		h.add_child(l)
		var s := HSlider.new()
		s.min_value = 0.0
		s.max_value = 1.0
		s.step = 0.05
		s.value = Game.settings[spec[1]]
		s.custom_minimum_size = Vector2(260, 40)
		var key: String = spec[1]
		s.value_changed.connect(func(x): Game.settings[key] = x; Game.apply_settings())
		h.add_child(s)
		v.add_child(h)
	v.add_child(_option_row("Gráficos", ["Baixo", "Médio", "Alto"], ["low", "medium", "high"].find(Game.settings.quality),
		func(i): Game.settings.quality = ["low", "medium", "high"][i]))
	v.add_child(_option_row("Tela cheia", ["Não", "Sim"], 1 if Game.settings.fullscreen else 0,
		func(i): Game.settings.fullscreen = i == 1; Game.apply_settings()))
	v.add_child(_button("Voltar", _back))


func _process(dt: float) -> void:
	_t += dt
	for i in _letters.size():
		var l := _letters[i]
		l.position.y = (0.0 if i < 5 else 150.0) + sin(_t * 3.0 + i * 0.5) * 8.0
		l.rotation = sin(_t * 2.0 + i * 0.7) * 0.04
	press.modulate.a = 0.55 + 0.45 * sin(_t * 4.0)


func _unhandled_input(e: InputEvent) -> void:
	if not _started and (e.is_action_pressed("ui_accept") or e.is_action_pressed("ui_accept_alt") or e.is_action_pressed("pause")):
		_started = true
		press.visible = false
		Audio.play("ui_start", -2.0)
		menu.visible = true
		for i in menu.get_child_count():
			UIKit.pop_in(menu.get_child(i), 0.06 * i)
		(menu.get_child(0) as Button).grab_focus()
		create_tween().tween_property(logo, "scale", Vector2(0.62, 0.62), 0.5).set_trans(Tween.TRANS_BACK)
		create_tween().tween_property(logo, "position", Vector2(-420, 20), 0.5).set_trans(Tween.TRANS_BACK)
		get_viewport().set_input_as_handled()
	elif e.is_action_pressed("ui_cancel") and (setup_panel.visible or options_panel.visible):
		_back()


func _open_setup() -> void:
	menu.visible = false
	setup_panel.visible = true
	UIKit.pop_in(setup_panel)
	(setup_panel.get_child(0).get_child(4) as Button).grab_focus()


func _open_options() -> void:
	menu.visible = false
	options_panel.visible = true
	UIKit.pop_in(options_panel)
	(options_panel.get_child(0).get_child(1).get_child(1) as Control).grab_focus()


func _back() -> void:
	Game.save()
	Audio.play("ui_back", -4.0)
	setup_panel.visible = false
	options_panel.visible = false
	menu.visible = true
	(menu.get_child(0) as Button).grab_focus()


func _start_race() -> void:
	Game.save()
	Audio.stop_music(0.4)
	Game.goto_scene("res://scenes/race.tscn")


func _garage() -> void:
	Game.goto_scene("res://scenes/garage.tscn")


func _quit() -> void:
	Game.save()
	get_tree().quit()
