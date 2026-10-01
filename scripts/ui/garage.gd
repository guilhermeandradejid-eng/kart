extends Node
## Garage: customise the kart part by part. Every swap rebuilds that slot with a
## squash-and-stretch pop, sparkles and a ratchet sound; stat bars tween to the
## new values with green/red deltas. Paint: primary / secondary / rims / livery.

const SLOTS := ["body", "wheels", "wing", "engine", "paint"]
const SLOT_LABELS := {"body": "Carroceria", "wheels": "Rodas", "wing": "Aerofólio", "engine": "Motor", "paint": "Pintura"}
const SWATCHES := ["e0342c", "ff8a1f", "ffd23f", "24b04a", "1fb7c9", "2f6fe0", "9b4be0", "ff5fa2", "f2f2f2", "2a2a33",
	"8a5a33", "5ee0ff"]

var showroom: Showroom
var ui: Control
var slot_i := 0
var tabs: HBoxContainer
var body_box: VBoxContainer
var stat_bars := {}
var stat_vals := {}
var cfg: KartConfig


func _ready() -> void:
	cfg = Game.player_config
	showroom = Showroom.new()
	showroom.garage = true
	add_child(showroom)
	showroom.cam_target = Vector3(-0.9, 0.55, 0)
	showroom.cam_dist = 4.4
	showroom.cam_height = 1.2
	showroom.cam_yaw = 0.75
	var layer := CanvasLayer.new()
	add_child(layer)
	ui = Control.new()
	ui.set_anchors_preset(Control.PRESET_FULL_RECT)
	ui.theme = UIKit.theme()
	layer.add_child(ui)
	var title := UIKit.label("GARAGEM", 84, true, UIKit.YELLOW, 16)
	title.position = Vector2(70, 34)
	ui.add_child(title)
	tabs = HBoxContainer.new()
	tabs.position = Vector2(70, 150)
	tabs.add_theme_constant_override("separation", 10)
	ui.add_child(tabs)
	for i in SLOTS.size():
		var b := Button.new()
		b.text = SLOT_LABELS[SLOTS[i]]
		b.add_theme_font_size_override("font_size", 26)
		b.pressed.connect(_select_slot.bind(i))
		b.focus_entered.connect(func(): Audio.play("ui_move", -8.0))
		tabs.add_child(b)
	var panel := PanelContainer.new()
	panel.position = Vector2(70, 240)
	panel.size = Vector2(640, 560)
	ui.add_child(panel)
	body_box = VBoxContainer.new()
	body_box.add_theme_constant_override("separation", 16)
	panel.add_child(body_box)
	_build_stats()
	var done := Button.new()
	done.text = "Pronto!"
	done.custom_minimum_size = Vector2(300, 80)
	done.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	done.position = Vector2(-380, -130)
	done.pressed.connect(_done)
	ui.add_child(done)
	var hint := UIKit.label("◀ ▶ trocar peça   •   Q/E categoria   •   ESC voltar", 22, false, Color(1, 1, 1, 0.7), 4)
	hint.set_anchors_preset(Control.PRESET_BOTTOM_LEFT)
	hint.position = Vector2(70, -60)
	ui.add_child(hint)
	_select_slot(0)
	_refresh_stats(true)
	Audio.music("music_menu", 1.0)


func _build_stats() -> void:
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	panel.position = Vector2(-560, 150)
	panel.size = Vector2(490, 440)
	ui.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 12)
	panel.add_child(v)
	v.add_child(UIKit.label("Desempenho", 40, true, UIKit.TEAL, 10))
	for k in KartParts.STAT_NAMES:
		var row := HBoxContainer.new()
		var l := UIKit.label(KartParts.STAT_NAMES[k], 24)
		l.custom_minimum_size = Vector2(170, 0)
		row.add_child(l)
		var bar := ProgressBar.new()
		bar.min_value = 0.0
		bar.max_value = 6.0
		bar.show_percentage = false
		bar.custom_minimum_size = Vector2(250, 26)
		var bg := StyleBoxFlat.new()
		bg.bg_color = Color(1, 1, 1, 0.1)
		bg.set_corner_radius_all(13)
		var fg := StyleBoxFlat.new()
		fg.bg_color = UIKit.YELLOW
		fg.set_corner_radius_all(13)
		bar.add_theme_stylebox_override("background", bg)
		bar.add_theme_stylebox_override("fill", fg)
		bar.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(bar)
		v.add_child(row)
		stat_bars[k] = bar


func _refresh_stats(instant := false) -> void:
	var s := KartParts.stats_for(cfg)
	for k in stat_bars:
		var bar: ProgressBar = stat_bars[k]
		var old: float = stat_vals.get(k, s[k])
		var fg := bar.get_theme_stylebox("fill") as StyleBoxFlat
		fg.bg_color = UIKit.YELLOW if absf(s[k] - old) < 0.01 else (Color("5ee07a") if s[k] > old else UIKit.RED)
		if instant:
			bar.value = s[k]
		else:
			var tw := create_tween()
			tw.tween_property(bar, "value", s[k], 0.45).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
			tw.tween_callback(func(): fg.bg_color = UIKit.YELLOW).set_delay(0.6)
		stat_vals[k] = s[k]


func _select_slot(i: int) -> void:
	slot_i = posmod(i, SLOTS.size())
	for c in body_box.get_children():
		c.queue_free()
	var slot: String = SLOTS[slot_i]
	body_box.add_child(UIKit.label(SLOT_LABELS[slot], 48, true, UIKit.YELLOW, 12))
	if slot == "paint":
		_paint_row("Cor principal", "color_primary")
		_paint_row("Cor secundária", "color_secondary")
		_paint_row("Rodas", "color_rim")
		_cycle_row("Pintura", KartParts.PATTERNS, cfg.pattern, func(j): cfg.pattern = j; showroom.kart_model.refresh_paint(); Audio.play("ui_color", -3.0))
	else:
		var ids: Array = KartParts.CATALOG[slot].keys()
		var names: Array = ids.map(func(id): return KartParts.CATALOG[slot][id].name)
		_cycle_row("Modelo", names, ids.find(cfg.get(slot)), func(j): _swap(slot, ids[j]))
		var d: Dictionary = KartParts.part(slot, cfg.get(slot)).stats
		var txt := ""
		for k in d:
			txt += "%s %s%.1f   " % [KartParts.STAT_NAMES[k], "+" if d[k] > 0 else "", d[k]]
		body_box.add_child(UIKit.label(txt if txt != "" else "Equilibrado", 22, false, Color(1, 1, 1, 0.75), 4))
	(tabs.get_child(slot_i) as Button).grab_focus()
	for j in body_box.get_child_count():
		UIKit.pop_in(body_box.get_child(j), 0.04 * j)


func _cycle_row(title: String, names: Array, sel: int, cb: Callable) -> void:
	var h := HBoxContainer.new()
	h.add_theme_constant_override("separation", 14)
	var t := UIKit.label(title, 28)
	t.custom_minimum_size = Vector2(150, 0)
	h.add_child(t)
	var left := Button.new()
	left.text = "◀"
	var val := UIKit.label(str(names[maxi(sel, 0)]), 34, true, UIKit.CREAM)
	val.custom_minimum_size = Vector2(250, 0)
	val.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var right := Button.new()
	right.text = "▶"
	var st := {"i": maxi(sel, 0)}
	var step := func(d: int):
		st.i = posmod(st.i + d, names.size())
		val.text = str(names[st.i])
		UIKit.punch(val, 1.3, 0.35)
		cb.call(st.i)
	left.pressed.connect(step.bind(-1))
	right.pressed.connect(step.bind(1))
	h.add_child(left)
	h.add_child(val)
	h.add_child(right)
	h.set_meta("step", step)
	body_box.add_child(h)


func _paint_row(title: String, prop: String) -> void:
	body_box.add_child(UIKit.label(title, 26))
	var g := GridContainer.new()
	g.columns = 12
	g.add_theme_constant_override("h_separation", 8)
	for hx in SWATCHES:
		var b := Button.new()
		b.custom_minimum_size = Vector2(40, 40)
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(hx)
		sb.set_corner_radius_all(20)
		sb.set_border_width_all(3)
		sb.border_color = Color(1, 1, 1, 0.9) if Color(hx).is_equal_approx(cfg.get(prop)) else Color(0, 0, 0, 0.5)
		for st in ["normal", "hover", "pressed", "focus"]:
			b.add_theme_stylebox_override(st, sb)
		b.pressed.connect(func():
			cfg.set(prop, Color(hx))
			showroom.kart_model.refresh_paint()
			Audio.play("ui_color", -3.0)
			Fx.burst("pickup", showroom.kart_model.global_position + Vector3.UP * 0.8, Vector3.UP, Color(hx), 0.8)
			_select_slot(slot_i))
		g.add_child(b)
	body_box.add_child(g)


func _swap(slot: String, id: String) -> void:
	showroom.kart_model.swap_part(slot, id)
	Audio.play("ui_swap_part", -2.0, randf_range(0.95, 1.08))
	Fx.burst("stars", showroom.kart_model.global_position + Vector3.UP * 0.7, Vector3.UP, Color.WHITE, 0.9)
	Fx.burst("poof", showroom.kart_model.global_position + Vector3.UP * 0.3, Vector3.UP, Color.WHITE, 0.7)
	showroom.driver.fire("action", "cheer")
	_refresh_stats()
	_select_slot(slot_i)


func _unhandled_input(e: InputEvent) -> void:
	if e.is_action_pressed("look_back") or (e is InputEventKey and (e as InputEventKey).pressed and (e as InputEventKey).physical_keycode == KEY_Q):
		_select_slot(slot_i - 1)
	elif e.is_action_pressed("item"):
		_select_slot(slot_i + 1)
	elif e.is_action_pressed("ui_left") or e.is_action_pressed("ui_right"):
		var row := body_box.get_child(1) if body_box.get_child_count() > 1 else null
		if row and row.has_meta("step"):
			(row.get_meta("step") as Callable).call(-1 if e.is_action_pressed("ui_left") else 1)
			get_viewport().set_input_as_handled()
	elif e.is_action_pressed("ui_cancel") or e.is_action_pressed("pause"):
		_done()


func _done() -> void:
	Game.save()
	Audio.play("ui_back", -3.0)
	Game.goto_scene("res://scenes/main_menu.tscn")
