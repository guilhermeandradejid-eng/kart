class_name Minimap
extends Control
## Top-down track outline with kart markers (player enlarged, rivals in their
## paint colour, leader crowned with a gold ring).

var race: RaceManager
var _pts := PackedVector2Array()
var _scale := 1.0
var _offset := Vector2.ZERO
var _center := Vector2.ZERO


func setup(r: RaceManager) -> void:
	race = r
	var t := r.track
	var mn := Vector2(INF, INF)
	var mx := Vector2(-INF, -INF)
	var raw := PackedVector2Array()
	for i in range(0, t.n, 3):
		var p := Vector2(t.pos[i].x, t.pos[i].z)
		raw.append(p)
		mn = mn.min(p)
		mx = mx.max(p)
	_center = (mn + mx) * 0.5
	var ext := mx - mn
	_scale = minf((size.x - 30.0) / ext.x, (size.y - 30.0) / ext.y)
	_offset = size * 0.5
	for p in raw:
		_pts.append(_map(p))
	_pts.append(_pts[0])


func _map(p: Vector2) -> Vector2:
	return (p - _center) * _scale + _offset


func _process(_dt: float) -> void:
	queue_redraw()


func _draw() -> void:
	if race == null or _pts.is_empty():
		return
	draw_polyline(_pts, Color(0.07, 0.08, 0.16, 0.85), 16.0, true)
	draw_polyline(_pts, Color(1, 1, 1, 0.9), 8.0, true)
	var t := race.track
	var st := t.transform_at(t.data.start_s, 0.0, 0.0)
	var sp := _map(Vector2(st.origin.x, st.origin.z))
	var sr := Vector2(st.basis.x.x, st.basis.x.z).normalized() * 9.0
	draw_line(sp - sr, sp + sr, UIKit.RED, 4.0)
	var leader: Kart = race.order[0] if race.order.size() > 0 else null
	for k in race.karts:
		if k == race.player:
			continue
		var p := _map(Vector2(k.global_position.x, k.global_position.z))
		if k == leader:
			draw_circle(p, 11.0, UIKit.YELLOW)
		draw_circle(p, 8.0, UIKit.INK)
		draw_circle(p, 6.0, k.config.color_primary)
	var pk := race.player
	if pk:
		var p := _map(Vector2(pk.global_position.x, pk.global_position.z))
		var f := Vector2(pk.forward().x, pk.forward().z).normalized()
		var tri := PackedVector2Array([p + f * 16.0, p + f.orthogonal() * 10.0 - f * 8.0, p - f.orthogonal() * 10.0 - f * 8.0])
		draw_colored_polygon(tri, UIKit.INK)
		draw_circle(p, 10.0, UIKit.INK)
		draw_circle(p, 7.5, UIKit.YELLOW)
