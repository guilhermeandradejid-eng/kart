class_name SkidMarks
extends Node3D
## Persistent tyre marks. Each wheel "trail" adds quads as it moves; quads live
## in a ring of chunk meshes so only the current chunk is rebuilt. Vertex
## colour = tint + opacity, UV.x = birth time (the shader fades marks out).

const CHUNKS := 48
const QUADS_PER_CHUNK := 96
const MIN_STEP := 0.32
const LIFE := 14.0

static var instance: SkidMarks

var _chunks: Array[MeshInstance3D] = []
var _data: Array = []          # per chunk: Array of quads [a_l, a_r, b_l, b_r, color, t0]
var _cur := 0
var _dirty := false
var _trails := {}              # id -> {"p": Vector3, "l": Vector3, "r": Vector3}
var _mat: ShaderMaterial
var _t := 0.0


func _ready() -> void:
	instance = self
	_mat = ShaderMaterial.new()
	_mat.shader = load("res://shaders/fx/skid.gdshader")
	_mat.set_shader_parameter("life", LIFE)
	for i in CHUNKS:
		var mi := MeshInstance3D.new()
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		mi.material_override = _mat
		add_child(mi)
		_chunks.append(mi)
		_data.append([])


func _exit_tree() -> void:
	if instance == self:
		instance = null


## Called every frame a wheel should leave a mark.
func mark(id: int, pos: Vector3, normal: Vector3, side: Vector3, width: float, color: Color) -> void:
	var p := pos + normal * 0.025
	var half := side.normalized() * width * 0.5
	var tr: Dictionary = _trails.get(id, {})
	if tr.is_empty():
		_trails[id] = {"p": p, "l": p - half, "r": p + half}
		return
	if p.distance_to(tr.p) < MIN_STEP:
		return
	if p.distance_to(tr.p) > 3.0:      # teleport / respawn: restart the trail
		_trails[id] = {"p": p, "l": p - half, "r": p + half}
		return
	var l := p - half
	var r := p + half
	_add_quad(tr.l, tr.r, l, r, color)
	tr.p = p
	tr.l = l
	tr.r = r


func lift(id: int) -> void:
	_trails.erase(id)


func _add_quad(al: Vector3, ar: Vector3, bl: Vector3, br: Vector3, color: Color) -> void:
	var chunk: Array = _data[_cur]
	if chunk.size() >= QUADS_PER_CHUNK:
		_rebuild(_cur)
		_cur = (_cur + 1) % CHUNKS
		chunk = _data[_cur]
		chunk.clear()
	chunk.append([al, ar, bl, br, color, Time.get_ticks_msec() / 1000.0])
	_dirty = true


func _process(dt: float) -> void:
	_t += dt
	_mat.set_shader_parameter("now", Time.get_ticks_msec() / 1000.0)
	if _dirty and _t > 0.05:
		_t = 0.0
		_dirty = false
		_rebuild(_cur)


func _rebuild(i: int) -> void:
	var chunk: Array = _data[i]
	if chunk.is_empty():
		_chunks[i].mesh = null
		return
	var v := PackedVector3Array()
	var c := PackedColorArray()
	var uv := PackedVector2Array()
	var idx := PackedInt32Array()
	for q in chunk:
		var base := v.size()
		v.append(q[0]); v.append(q[1]); v.append(q[2]); v.append(q[3])
		for k in 4:
			c.append(q[4])
			uv.append(Vector2(q[5], float(k % 2)))
		idx.append_array([base, base + 2, base + 1, base + 1, base + 2, base + 3])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = v
	arr[Mesh.ARRAY_COLOR] = c
	arr[Mesh.ARRAY_TEX_UV] = uv
	arr[Mesh.ARRAY_INDEX] = idx
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	_chunks[i].mesh = m
