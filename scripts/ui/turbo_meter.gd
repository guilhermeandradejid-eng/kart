class_name TurboMeter
extends Control
## CTR-style gauge: the arc fills with the drift charge in the colour of the
## current spark tier; while boosting it turns into a flickering flame bar.

const TIER_COLORS := [Color(0.85, 0.88, 1.0), Color(0.3, 0.65, 1.0), Color(1.0, 0.55, 0.12), Color(0.85, 0.35, 1.0)]
var kart: Kart
var _fill := 0.0
var _boost := 0.0
var _t := 0.0


func _process(dt: float) -> void:
	_t += dt
	if kart == null:
		return
	var target := clampf(kart.drift_charge / 3.0, 0.0, 1.0) if kart.drifting else 0.0
	_fill = lerpf(_fill, target, 1.0 - exp(-dt * 12.0))
	_boost = lerpf(_boost, clampf(kart.boost_time / 1.7, 0.0, 1.0), 1.0 - exp(-dt * 10.0))
	queue_redraw()


func _draw() -> void:
	var c := Vector2(size.x * 0.5, size.y * 0.95)
	var r := minf(size.x * 0.45, size.y * 0.9)
	var a0 := PI * 1.05
	var a1 := PI * 1.95
	draw_arc(c, r, a0, a1, 48, Color(0.07, 0.08, 0.16, 0.8), 30.0, true)
	draw_arc(c, r, a0, a1, 48, Color(1, 1, 1, 0.12), 22.0, true)
	for k in 3:
		var at: float = a0 + (a1 - a0) * float(Kart.DRIFT_TIERS[k]) / 3.0
		draw_line(c + Vector2(cos(at), sin(at)) * (r - 16), c + Vector2(cos(at), sin(at)) * (r + 16), Color(1, 1, 1, 0.5), 3.0)
	if _boost > 0.01:
		var flick := 0.85 + 0.15 * sin(_t * 40.0)
		draw_arc(c, r, a0, a0 + (a1 - a0) * _boost, 40, Color(1.0, 0.45 * flick, 0.08), 22.0, true)
		draw_arc(c, r - 4, a0, a0 + (a1 - a0) * _boost, 40, Color(1.0, 0.9, 0.4, 0.8), 8.0, true)
	elif _fill > 0.01 and kart:
		var col: Color = TIER_COLORS[kart.drift_tier_level]
		draw_arc(c, r, a0, a0 + (a1 - a0) * _fill, 40, col, 22.0, true)
		draw_arc(c, r - 5, a0, a0 + (a1 - a0) * _fill, 40, Color(1, 1, 1, 0.55), 5.0, true)
	var f := UIKit.display_font if UIKit.display_font else ThemeDB.fallback_font
	draw_string_outline(f, c + Vector2(-48, -r * 0.25), "TURBO", HORIZONTAL_ALIGNMENT_CENTER, 96, 26, 8, UIKit.INK)
	draw_string(f, c + Vector2(-48, -r * 0.25), "TURBO", HORIZONTAL_ALIGNMENT_CENTER, 96, 26,
		Color(1.0, 0.7, 0.25) if _boost > 0.01 else UIKit.CREAM)
