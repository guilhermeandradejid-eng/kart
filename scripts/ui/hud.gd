extends CanvasLayer
## Race HUD: position (bouncy, colour-coded), lap, timer, item roulette slot,
## golden shells, speedometer, minimap, countdown, callouts, wrong-way banner,
## screen FX (speed blur / lines / aberration), pause menu and results.

var race: RaceManager
var player: Kart
var root: Control
var pos_label: Label
var pos_suffix: Label
var lap_label: Label
var time_label: Label
var speed_label: Label
var shell_label: Label
var shell_icon: ItemIcon
var item_panel: Panel
var item_icon: ItemIcon
var center_label: Label
var msg_label: Label
var wrong_label: Label
var minimap: Minimap
var fx_rect: ColorRect
var fx_mat: ShaderMaterial
var pause_panel: Control
var results_panel: Control
var _roll_t := 0.0
var _aberr := 0.0
var _last_pos := 0
var _items := ["pepper", "banana", "coconut"]


func bind(r: RaceManager) -> void:
	race = r
	player = r.player
	layer = 10
	_build()
	r.countdown_tick.connect(_on_countdown)
	r.message.connect(_on_message)
	r.wrong_way.connect(_on_wrong_way)
	r.race_finished.connect(_on_results)
	r.positions_changed.connect(_on_positions)
	player.item_changed.connect(_on_item)
	player.shells_changed.connect(_on_shells)
	player.bumped.connect(func(s, _p, _n, _o): _aberr = maxf(_aberr, clampf(s / 15.0, 0.2, 1.0)))
	player.spun_out.connect(func(_k): _aberr = 1.0)
	player.boosted.connect(func(_k, _d): _aberr = maxf(_aberr, 0.35))


func _build() -> void:
	root = Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = UIKit.theme()
	add_child(root)
	# screen fx underlay
	fx_rect = ColorRect.new()
	fx_rect.set_anchors_preset(Control.PRESET_FULL_RECT)
	fx_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	fx_mat = ShaderMaterial.new()
	fx_mat.shader = load("res://shaders/ui/screen_fx.gdshader")
	fx_rect.material = fx_mat
	fx_mat.set_shader_parameter("blur", 0.0)
	fx_mat.set_shader_parameter("lines", 0.0)
	fx_mat.set_shader_parameter("aberration", 0.0)
	root.add_child(fx_rect)
	# position (top right)
	pos_label = UIKit.label("8", 150, true, Color.WHITE, 16)
	pos_label.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	pos_label.position = Vector2(-270, 6)
	pos_label.size = Vector2(170, 170)
	pos_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	root.add_child(pos_label)
	pos_suffix = UIKit.label("º", 64, true, Color.WHITE, 12)
	pos_suffix.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	pos_suffix.position = Vector2(-98, 28)
	root.add_child(pos_suffix)
	lap_label = UIKit.label("VOLTA 1/3", 40, true)
	lap_label.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	lap_label.position = Vector2(-300, 172)
	lap_label.size = Vector2(260, 50)
	lap_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	root.add_child(lap_label)
	time_label = UIKit.label("0:00.00", 38, true, UIKit.YELLOW)
	time_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	time_label.position = Vector2(-110, 18)
	time_label.size = Vector2(220, 50)
	time_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	root.add_child(time_label)
	# item slot (top left)
	item_panel = Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.08, 0.16, 0.8)
	sb.set_corner_radius_all(40)
	sb.border_color = UIKit.YELLOW
	sb.set_border_width_all(6)
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 10
	item_panel.add_theme_stylebox_override("panel", sb)
	item_panel.position = Vector2(34, 30)
	item_panel.size = Vector2(150, 150)
	root.add_child(item_panel)
	item_icon = ItemIcon.new()
	item_icon.set_anchors_preset(Control.PRESET_FULL_RECT)
	item_icon.offset_left = 18
	item_icon.offset_top = 18
	item_icon.offset_right = -18
	item_icon.offset_bottom = -18
	item_panel.add_child(item_icon)
	# shells + speed (bottom right)
	shell_icon = ItemIcon.new()
	shell_icon.item = "shell"
	shell_icon.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	shell_icon.position = Vector2(-250, -120)
	shell_icon.size = Vector2(70, 70)
	root.add_child(shell_icon)
	shell_label = UIKit.label("x0", 52, true, UIKit.YELLOW, 12)
	shell_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	shell_label.position = Vector2(-172, -118)
	root.add_child(shell_label)
	speed_label = UIKit.label("0 km/h", 30, true, UIKit.CREAM)
	speed_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	speed_label.position = Vector2(-250, -52)
	root.add_child(speed_label)
	# minimap (bottom left)
	minimap = Minimap.new()
	minimap.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	minimap.position = Vector2(26, -300)
	minimap.size = Vector2(300, 270)
	root.add_child(minimap)
	minimap.setup(race)
	# centre callouts
	center_label = UIKit.label("", 210, true, UIKit.YELLOW, 22)
	center_label.set_anchors_preset(Control.PRESET_CENTER)
	center_label.size = Vector2(900, 260)
	center_label.position = Vector2(-450, -230)
	center_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	center_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	root.add_child(center_label)
	msg_label = UIKit.label("", 72, true, Color.WHITE, 14)
	msg_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	msg_label.size = Vector2(1400, 110)
	msg_label.position = Vector2(-700, 180)
	msg_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	root.add_child(msg_label)
	wrong_label = UIKit.label("CONTRAMÃO!", 96, true, UIKit.RED, 18)
	wrong_label.set_anchors_preset(Control.PRESET_CENTER)
	wrong_label.size = Vector2(1000, 140)
	wrong_label.position = Vector2(-500, -60)
	wrong_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	wrong_label.visible = false
	root.add_child(wrong_label)
	_build_pause()


func _build_pause() -> void:
	pause_panel = Control.new()
	pause_panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	pause_panel.process_mode = Node.PROCESS_MODE_ALWAYS
	pause_panel.visible = false
	root.add_child(pause_panel)
	var dim := ColorRect.new()
	dim.color = Color(0.03, 0.03, 0.08, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	pause_panel.add_child(dim)
	var box := VBoxContainer.new()
	box.set_anchors_preset(Control.PRESET_CENTER)
	box.position = Vector2(-220, -200)
	box.size = Vector2(440, 400)
	box.add_theme_constant_override("separation", 18)
	pause_panel.add_child(box)
	var title := UIKit.label("PAUSA", 96, true, UIKit.YELLOW, 16)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)
	for pair in [["Continuar", _toggle_pause], ["Reiniciar", func(): race.restart()], ["Menu Principal", func(): race.quit_to_menu()]]:
		var b := Button.new()
		b.text = pair[0]
		b.pressed.connect(pair[1])
		b.focus_entered.connect(func(): Audio.play("ui_move", -6.0))
		box.add_child(b)


func _toggle_pause() -> void:
	if race.state == "finished" and results_panel:
		return
	var p := not get_tree().paused
	get_tree().paused = p
	pause_panel.visible = p
	Audio.play("ui_select" if p else "ui_back", -3.0)
	if p:
		(pause_panel.get_child(1).get_child(1) as Button).grab_focus()


func _unhandled_input(e: InputEvent) -> void:
	if e.is_action_pressed("pause"):
		_toggle_pause()
		get_viewport().set_input_as_handled()


# ---------------------------------------------------------------- updates

func _process(dt: float) -> void:
	if race == null or player == null:
		return
	var pos := race.position_of(player)
	pos_label.text = str(pos)
	var col: Color = UIKit.POSITION_COLORS[clampi(pos - 1, 0, 7)]
	pos_label.add_theme_color_override("font_color", col)
	pos_suffix.add_theme_color_override("font_color", col)
	lap_label.text = "VOLTA %d/%d" % [race.lap_of(player), race.laps]
	time_label.text = UIKit.time_str(race.race_time)
	var kmh := int(absf(player.speed) * 3.6 * 1.25)
	speed_label.text = "%d km/h" % kmh
	# roulette
	if player.item_rolling > 0.0:
		_roll_t += dt
		var idx := int(_roll_t * 14.0) % _items.size()
		if item_icon.item != _items[idx]:
			item_icon.item = _items[idx]
			item_icon.queue_redraw()
			Audio.play("ui_move", -12.0, 1.3)
	# screen fx
	var sp := player.speed_ratio()
	var boosting := player.boost_time > 0.0
	_aberr = move_toward(_aberr, 0.0, dt * 1.8)
	fx_mat.set_shader_parameter("blur", lerpf(fx_mat.get_shader_parameter("blur"), (0.55 if boosting else 0.0) + clampf(sp - 0.95, 0, 1) * 0.4, 1.0 - exp(-dt * 6.0)))
	fx_mat.set_shader_parameter("lines", lerpf(fx_mat.get_shader_parameter("lines"), (1.0 if boosting else clampf((sp - 0.95) * 3.0, 0, 0.5)), 1.0 - exp(-dt * 5.0)))
	fx_mat.set_shader_parameter("aberration", _aberr)
	var tint := Color(1.0, 0.55, 0.15, 0.07) if player.boost_kind.begins_with("mini3") else Color(1, 1, 1, 0)
	fx_mat.set_shader_parameter("tint", tint)


func _on_wrong_way(on: bool) -> void:
	wrong_label.visible = on
	if on:
		UIKit.punch(wrong_label, 1.4)


func _on_shells(n: int) -> void:
	shell_label.text = "x%d" % n
	UIKit.punch(shell_label, 1.5, 0.4)


func _on_positions() -> void:
	var pos := race.position_of(player)
	if pos != _last_pos:
		if _last_pos != 0 and pos < _last_pos:
			Audio.play("ui_move", -4.0, 1.6)
			if race.state == "race" and randf() < 0.35:
				player.driver.fire("action", "cheer")
		_last_pos = pos
		UIKit.punch(pos_label, 1.45, 0.6)


func _on_item(it: String, rolling: bool) -> void:
	if rolling:
		_roll_t = 0.0
		Audio.play("item_roulette", -6.0)
		UIKit.punch(item_panel, 1.2, 0.3)
	else:
		item_icon.item = it
		item_icon.queue_redraw()
		if it != "":
			Audio.play("item_get", -3.0)
			UIKit.punch(item_panel, 1.3, 0.5)


func _on_countdown(n: int) -> void:
	center_label.text = str(n) if n > 0 else "JÁ!"
	center_label.add_theme_color_override("font_color", [UIKit.TEAL, UIKit.RED, UIKit.ORANGE, UIKit.YELLOW][n] if n <= 3 else Color.WHITE)
	center_label.pivot_offset = center_label.size * 0.5
	center_label.modulate.a = 1.0
	UIKit.punch(center_label, 2.2, 0.5)
	var tw := create_tween()
	tw.tween_interval(0.55 if n > 0 else 0.8)
	tw.tween_property(center_label, "modulate:a", 0.0, 0.25)
	if n == 0:
		Juice.shake(0.15)


func _on_message(text: String, style: String) -> void:
	msg_label.text = text
	var color := Color.WHITE
	var size := 72
	match style:
		"big":
			color = UIKit.YELLOW
			size = 96
		"title":
			color = UIKit.CREAM
			size = 84
		"finish":
			color = UIKit.YELLOW
			size = 130
		"lap":
			color = UIKit.TEAL
	msg_label.add_theme_font_size_override("font_size", size)
	msg_label.add_theme_color_override("font_color", color)
	msg_label.modulate.a = 1.0
	msg_label.pivot_offset = msg_label.size * 0.5
	UIKit.punch(msg_label, 1.6, 0.6)
	var tw := create_tween()
	tw.tween_interval(2.2 if style != "finish" else 5.0)
	tw.tween_property(msg_label, "modulate:a", 0.0, 0.4)


func _on_results(results: Array) -> void:
	results_panel = PanelContainer.new()
	results_panel.set_anchors_preset(Control.PRESET_CENTER)
	results_panel.position = Vector2(-430, -380)
	results_panel.size = Vector2(860, 760)
	results_panel.process_mode = Node.PROCESS_MODE_ALWAYS
	root.add_child(results_panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 8)
	results_panel.add_child(v)
	var title := UIKit.label("RESULTADO", 76, true, UIKit.YELLOW, 14)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	v.add_child(title)
	for i in results.size():
		var r: Dictionary = results[i]
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 24)
		var c: Color = UIKit.POSITION_COLORS[mini(i, 7)] if i < 3 else (UIKit.YELLOW if r.player else UIKit.CREAM)
		var pl := UIKit.label(UIKit.ordinal(i + 1), 44, true, c)
		pl.custom_minimum_size = Vector2(90, 0)
		row.add_child(pl)
		var sw := ColorRect.new()
		sw.color = (r.config as KartConfig).color_primary
		sw.custom_minimum_size = Vector2(26, 26)
		sw.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(sw)
		var nl := UIKit.label(r.name + ("  (você)" if r.player else ""), 38, false, UIKit.YELLOW if r.player else UIKit.CREAM)
		nl.custom_minimum_size = Vector2(430, 0)
		row.add_child(nl)
		row.add_child(UIKit.label(UIKit.time_str(r.time), 38, true, c))
		v.add_child(row)
		UIKit.pop_in(row, 0.12 * i)
	var buttons := HBoxContainer.new()
	buttons.alignment = BoxContainer.ALIGNMENT_CENTER
	buttons.add_theme_constant_override("separation", 24)
	v.add_child(buttons)
	var again := Button.new()
	again.text = "Correr de novo"
	again.pressed.connect(func(): race.restart())
	buttons.add_child(again)
	var menu := Button.new()
	menu.text = "Menu"
	menu.pressed.connect(func(): race.quit_to_menu())
	buttons.add_child(menu)
	again.grab_focus.call_deferred()
	UIKit.pop_in(results_panel)
