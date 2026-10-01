extends Node
var track: Track
func _ready():
	track = Track.new()
	add_child(track)
	track.load_track("coconut_bay", false)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var space := get_viewport().world_3d.direct_space_state
	for dr in [1130, 1138, 1142, 1146, 1150, 1156]:
		var s: float = track.data.start_s + dr
		var line := "r=%d: " % dr
		for lat in [-8.0, -4.0, 0.0, 4.0, 8.0]:
			var fr := track.frame_at(s)
			var p: Vector3 = fr.p + fr.r * lat
			var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 6.0, p - Vector3.UP * 6.0)
			var r := space.intersect_ray(q)
			line += " [%+.0f: %s %.2f]" % [lat, r.collider.get_meta("surface", "?") if r else "none", (r.position.y - p.y) if r else 0.0]
		print(line, " tags=", track.tags[track.index_of_s(s)])
	get_tree().quit()
