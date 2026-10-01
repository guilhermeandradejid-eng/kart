class_name ItemIcon
extends Control
## Vector-drawn item icons (pepper / banana / coconut / shell) so the HUD has
## crisp, resolution-independent art with a chunky outline.

var item := ""
var outline := Color("121528")


func _draw() -> void:
	var c := size * 0.5
	var r := minf(size.x, size.y) * 0.42
	match item:
		"pepper":
			_pepper(c, r)
		"banana":
			_banana(c, r)
		"coconut":
			_coconut(c, r)
		"shell":
			_shell(c, r)


func _poly_outlined(pts: PackedVector2Array, fill: Color, w := 5.0) -> void:
	var closed := pts.duplicate()
	closed.append(pts[0])
	draw_polyline(closed, outline, w * 2.0, true)
	draw_colored_polygon(pts, fill)


func _pepper(c: Vector2, r: float) -> void:
	var pts := PackedVector2Array()
	for i in 24:
		var t := float(i) / 23.0
		var y := lerpf(-0.75, 0.95, t)
		var wdt := 0.42 * sin(PI * clampf(t * 1.05, 0, 1)) * (1.0 - t * 0.35)
		pts.append(c + Vector2(wdt + sin(t * 3.0) * 0.25, y).rotated(-0.5) * r)
	for i in range(23, -1, -1):
		var t := float(i) / 23.0
		var y := lerpf(-0.75, 0.95, t)
		var wdt := 0.42 * sin(PI * clampf(t * 1.05, 0, 1)) * (1.0 - t * 0.35)
		pts.append(c + Vector2(-wdt + sin(t * 3.0) * 0.25, y).rotated(-0.5) * r)
	_poly_outlined(pts, Color("e8322c"))
	draw_line(c + Vector2(-0.25, -0.6).rotated(-0.5) * r, c + Vector2(-0.05, -0.2).rotated(-0.5) * r, Color(1, 1, 1, 0.55), r * 0.1, true)
	var stem := PackedVector2Array([c + Vector2(-0.12, -0.72).rotated(-0.5) * r, c + Vector2(0.14, -0.72).rotated(-0.5) * r,
		c + Vector2(0.25, -1.05).rotated(-0.5) * r, c + Vector2(0.1, -1.08).rotated(-0.5) * r])
	_poly_outlined(stem, Color("3ca83c"), 4.0)


func _banana(c: Vector2, r: float) -> void:
	var pts := PackedVector2Array()
	for i in 20:
		var a := lerpf(-2.4, -0.7, float(i) / 19.0)
		pts.append(c + Vector2(cos(a), sin(a)) * r * 1.0 + Vector2(0, r * 0.55))
	for i in range(19, -1, -1):
		var a := lerpf(-2.3, -0.8, float(i) / 19.0)
		pts.append(c + Vector2(cos(a), sin(a)) * r * 0.62 + Vector2(0, r * 0.35))
	_poly_outlined(pts, Color("ffd83a"))
	draw_circle(pts[0], r * 0.09, Color("6b4a1e"))
	draw_circle(pts[19], r * 0.09, Color("6b4a1e"))


func _coconut(c: Vector2, r: float) -> void:
	draw_circle(c + Vector2(0, r * 0.1), r * 0.78 + 5.0, outline)
	draw_circle(c + Vector2(0, r * 0.1), r * 0.78, Color("7a4a2a"))
	draw_circle(c + Vector2(-r * 0.25, -r * 0.15), r * 0.22, Color(1, 1, 1, 0.18))
	for p in [Vector2(-0.2, 0.05), Vector2(0.18, 0.05), Vector2(0.0, 0.32)]:
		draw_circle(c + p * r, r * 0.09, Color("3a2212"))
	draw_line(c + Vector2(0.35, -0.55) * r, c + Vector2(0.6, -0.95) * r, outline, r * 0.14, true)
	draw_line(c + Vector2(0.35, -0.55) * r, c + Vector2(0.6, -0.95) * r, Color("d8c08a"), r * 0.07, true)
	var t := Time.get_ticks_msec() * 0.02
	for i in 5:
		var a := t + i * 1.3
		draw_line(c + Vector2(0.62, -0.98) * r, c + Vector2(0.62, -0.98) * r + Vector2(cos(a), sin(a)) * r * 0.22, Color("ffe060"), 3.0)
	queue_redraw()


func _shell(c: Vector2, r: float) -> void:
	var pts := PackedVector2Array()
	for i in 21:
		var a := lerpf(PI + 0.25, TAU - 0.25, float(i) / 20.0)
		var rr := r * (0.92 + 0.06 * sin(i * PI))
		pts.append(c + Vector2(cos(a), sin(a)) * rr + Vector2(0, r * 0.3))
	pts.append(c + Vector2(r * 0.18, r * 0.65))
	pts.append(c + Vector2(-r * 0.18, r * 0.65))
	_poly_outlined(pts, Color("ffc93c"))
	for i in 5:
		var a := lerpf(PI + 0.55, TAU - 0.55, float(i) / 4.0)
		draw_line(c + Vector2(0, r * 0.55), c + Vector2(cos(a), sin(a)) * r * 0.8 + Vector2(0, r * 0.3), Color("d98a1f"), 3.0, true)
