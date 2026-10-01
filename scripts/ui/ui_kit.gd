class_name UIKit
extends RefCounted
## Shared UI styling: fonts, theme, palette and tween helpers so every screen
## has the same chunky, bouncy "toy" feel.

const YELLOW := Color("ffd23f")
const ORANGE := Color("ff8a1f")
const RED := Color("ef3b36")
const TEAL := Color("1fb7c9")
const NAVY := Color("1b2140")
const INK := Color("121528")
const CREAM := Color("fff6e0")
const POSITION_COLORS := [Color("ffd23f"), Color("dfe7f0"), Color("f0a35e"), Color("ffffff"), Color("ffffff"),
	Color("ffffff"), Color("ffffff"), Color("ffffff")]

static var _theme: Theme
static var display_font: Font
static var body_font: Font
static var bold_font: Font


static func fonts() -> void:
	if display_font:
		return
	display_font = load("res://assets/fonts/LilitaOne.woff2")
	body_font = load("res://assets/fonts/Fredoka-Medium.woff2")
	bold_font = load("res://assets/fonts/Fredoka-Bold.woff2")


static func theme() -> Theme:
	if _theme:
		return _theme
	fonts()
	var t := Theme.new()
	t.default_font = body_font
	t.default_font_size = 26
	var btn := StyleBoxFlat.new()
	btn.bg_color = NAVY
	btn.set_corner_radius_all(18)
	btn.border_color = Color(1, 1, 1, 0.15)
	btn.set_border_width_all(3)
	btn.content_margin_left = 28
	btn.content_margin_right = 28
	btn.content_margin_top = 10
	btn.content_margin_bottom = 12
	btn.shadow_color = Color(0, 0, 0, 0.35)
	btn.shadow_size = 8
	btn.shadow_offset = Vector2(0, 6)
	var hov := btn.duplicate() as StyleBoxFlat
	hov.bg_color = ORANGE
	hov.border_color = YELLOW
	var prs := hov.duplicate() as StyleBoxFlat
	prs.bg_color = RED
	for st in ["normal", "disabled"]:
		t.set_stylebox(st, "Button", btn)
	t.set_stylebox("hover", "Button", hov)
	t.set_stylebox("focus", "Button", hov)
	t.set_stylebox("pressed", "Button", prs)
	t.set_font("font", "Button", display_font)
	t.set_font_size("font_size", "Button", 34)
	t.set_color("font_color", "Button", CREAM)
	t.set_color("font_hover_color", "Button", INK)
	t.set_color("font_focus_color", "Button", INK)
	t.set_color("font_pressed_color", "Button", CREAM)
	t.set_font("font", "Label", body_font)
	t.set_color("font_color", "Label", CREAM)
	t.set_color("font_outline_color", "Label", INK)
	t.set_constant("outline_size", "Label", 8)
	var panel := StyleBoxFlat.new()
	panel.bg_color = Color(0.07, 0.08, 0.16, 0.86)
	panel.set_corner_radius_all(26)
	panel.border_color = Color(1, 1, 1, 0.12)
	panel.set_border_width_all(3)
	panel.content_margin_left = 30
	panel.content_margin_right = 30
	panel.content_margin_top = 24
	panel.content_margin_bottom = 24
	t.set_stylebox("panel", "PanelContainer", panel)
	_theme = t
	return t


static func label(text: String, size := 28, display := false, color := CREAM, outline := 8) -> Label:
	fonts()
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", display_font if display else body_font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.add_theme_color_override("font_outline_color", INK)
	l.add_theme_constant_override("outline_size", outline)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.35))
	l.add_theme_constant_override("shadow_offset_y", 5)
	l.add_theme_constant_override("shadow_offset_x", 0)
	return l


static func punch(c: Control, amount := 1.35, time := 0.45) -> void:
	c.pivot_offset = c.size * 0.5
	c.scale = Vector2.ONE * amount
	var tw := c.create_tween()
	tw.tween_property(c, "scale", Vector2.ONE, time).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)


static func pop_in(c: Control, delay := 0.0) -> void:
	c.pivot_offset = c.size * 0.5
	c.scale = Vector2.ZERO
	c.modulate.a = 0.0
	var tw := c.create_tween()
	tw.tween_interval(delay)
	tw.tween_property(c, "modulate:a", 1.0, 0.12)
	tw.parallel().tween_property(c, "scale", Vector2.ONE, 0.5).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


static func ordinal(n: int) -> String:
	return "%dº" % n


static func time_str(t: float) -> String:
	var m := int(t / 60.0)
	var s := fmod(t, 60.0)
	return "%d:%05.2f" % [m, s]
