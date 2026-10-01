class_name Driver
extends Node3D
## Guará in the kart. Builds an AnimationTree in code:
##
##   state (Transition: race | countdown | victory | victory_loop | lose | wave | idle)
##     race = Blend2(drive steer blend-space, drift blend-space) -> Blend2(look back)
##   -> OneShot hop -> OneShot land -> OneShot boost -> OneShot trick -> OneShot hit
##   -> OneShot action (throw/cheer) -> output
##
## On top of the baked clips (which already carry anticipation, overlap and
## squash/stretch) two procedural layers react to the real kart motion:
##   * SpringBoneSimulator3D on tail, ears, scarf and mane-less chains:
##     true follow-through on turns, bumps and landings.
##   * DriverHeadLook: the head turns INTO the upcoming corner before the kart
##     does (anticipation) and glances at nearby rivals (staging/acting).

const SCENE := "res://assets/models/characters/guara.glb"
const VARIANTS := [
	{"hue": 0.0, "sat": 1.0, "val": 1.0, "cloth_hue": 0.0},        # classic Guará
	{"hue": 0.0, "sat": 0.15, "val": 0.95, "cloth_hue": 0.45},     # silver
	{"hue": -0.03, "sat": 0.9, "val": 0.62, "cloth_hue": 0.72},    # chocolate
	{"hue": 0.08, "sat": 1.1, "val": 1.05, "cloth_hue": 0.3},      # golden
	{"hue": 0.52, "sat": 0.55, "val": 0.95, "cloth_hue": 0.14},    # blue-ish
	{"hue": 0.9, "sat": 0.8, "val": 0.95, "cloth_hue": 0.55},      # berry
	{"hue": 0.0, "sat": 0.0, "val": 1.25, "cloth_hue": 0.85},      # snow
	{"hue": 0.22, "sat": 0.7, "val": 0.85, "cloth_hue": 0.62},     # moss
]

var anim_player: AnimationPlayer
var tree: AnimationTree
var skeleton: Skeleton3D
var head_look: DriverHeadLook
var springs: SpringBoneSimulator3D
var variant := 0
var fur_mat: ShaderMaterial
var _state := "race"
var _victory_timer := 0.0
var _model: Node3D


func _init(v := 0) -> void:
	variant = v


func _ready() -> void:
	var ps := load(SCENE) as PackedScene
	if ps == null:
		return
	_model = ps.instantiate()
	add_child(_model)
	var var_d: Dictionary = VARIANTS[variant % VARIANTS.size()]
	fur_mat = Mats.shader_mat("res://shaders/fur.gdshader", {"hue": var_d.hue, "sat": var_d.sat, "val": var_d.val})
	var cloth := Mats.shader_mat("res://shaders/fur.gdshader", {"sheen": 0.15, "roughness_v": 0.9, "translucency": 0.05,
		"hue": var_d.cloth_hue})
	var scarf := Mats.shader_mat("res://shaders/fur.gdshader", {"sheen": 0.3, "roughness_v": 0.9, "translucency": 0.3,
		"hue": var_d.cloth_hue * 0.5})
	Mats.apply(_model, "character", {"Fur": fur_mat, "Cloth": cloth, "Scarf": scarf})
	anim_player = _model.find_child("AnimationPlayer", true, false)
	skeleton = _model.find_child("Skeleton3D", true, false)
	for mi in _model.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	if anim_player:
		_build_tree()
	if skeleton:
		_build_springs()
		head_look = DriverHeadLook.new()
		head_look.name = "HeadLook"
		skeleton.add_child(head_look)


# ---------------------------------------------------------------- tree

func _anim(name: String) -> AnimationNodeAnimation:
	var a := AnimationNodeAnimation.new()
	a.animation = name
	return a


func _bs(neg: String, mid: String, pos: String) -> AnimationNodeBlendSpace1D:
	var b := AnimationNodeBlendSpace1D.new()
	b.min_space = -1.0
	b.max_space = 1.0
	b.add_blend_point(_anim(neg), -1.0, -1, "neg")
	if mid != "":
		b.add_blend_point(_anim(mid), 0.0, -1, "mid")
	b.add_blend_point(_anim(pos), 1.0, -1, "pos")
	return b


func _oneshot(fade_in := 0.06, fade_out := 0.18) -> AnimationNodeOneShot:
	var o := AnimationNodeOneShot.new()
	o.fadein_time = fade_in
	o.fadeout_time = fade_out
	o.mix_mode = AnimationNodeOneShot.MIX_MODE_BLEND
	return o


func _build_tree() -> void:
	for n in ["drive_idle", "steer_L", "steer_R", "drift_L", "drift_R", "look_back", "countdown", "victory_loop",
			"lose", "wave", "stand_idle"]:
		var a := anim_player.get_animation(n)
		if a:
			a.loop_mode = Animation.LOOP_LINEAR
	var bt := AnimationNodeBlendTree.new()
	bt.add_node("steer", _bs("steer_L", "drive_idle", "steer_R"), Vector2(0, 0))
	bt.add_node("drift", _bs("drift_L", "", "drift_R"), Vector2(0, 200))
	bt.add_node("race_mix", AnimationNodeBlend2.new(), Vector2(250, 100))
	bt.connect_node("race_mix", 0, "steer")
	bt.connect_node("race_mix", 1, "drift")
	bt.add_node("look_anim", _anim("look_back"), Vector2(250, 300))
	bt.add_node("look", AnimationNodeBlend2.new(), Vector2(450, 100))
	bt.connect_node("look", 0, "race_mix")
	bt.connect_node("look", 1, "look_anim")
	var tr := AnimationNodeTransition.new()
	tr.xfade_time = 0.25
	var states := ["race", "countdown", "victory", "victory_loop", "lose", "wave", "idle"]
	for s in states:
		tr.add_input(s)
	bt.add_node("state", tr, Vector2(650, 100))
	bt.connect_node("state", 0, "look")
	var clips := {"countdown": "countdown", "victory": "victory", "victory_loop": "victory_loop", "lose": "lose",
		"wave": "wave", "idle": "stand_idle"}
	var idx := 1
	for s in states.slice(1):
		bt.add_node("st_" + s, _anim(clips[s]), Vector2(450, 300 + idx * 80))
		bt.connect_node("state", idx, "st_" + s)
		idx += 1
	var prev := "state"
	var x := 850
	for os in [["hop", "hop", 0.04, 0.12], ["land", "land", 0.03, 0.15], ["boost", "boost", 0.05, 0.3],
			["trick", "trick_a", 0.05, 0.2], ["hit", "hit_spin", 0.05, 0.25], ["action", "throw_fwd", 0.06, 0.2]]:
		var name: String = os[0]
		bt.add_node("os_" + name, _oneshot(os[2], os[3]), Vector2(x, 100))
		bt.add_node("clip_" + name, _anim(os[1]), Vector2(x, 300))
		bt.connect_node("os_" + name, 0, prev)
		bt.connect_node("os_" + name, 1, "clip_" + name)
		prev = "os_" + name
		x += 200
	bt.connect_node("output", 0, prev)
	tree = AnimationTree.new()
	tree.name = "AnimationTree"
	tree.tree_root = bt
	_model.add_child(tree)
	tree.anim_player = tree.get_path_to(anim_player)
	tree.active = true
	tree.set("parameters/state/transition_request", "race")


func _build_springs() -> void:
	springs = SpringBoneSimulator3D.new()
	springs.name = "Springs"
	skeleton.add_child(springs)
	var chains := [
		["tail.0", "tail.3", 1.1, 0.35, 0.4, 0.06],
		["ear.L.0", "ear.L.1", 2.6, 0.45, 0.0, 0.03],
		["ear.R.0", "ear.R.1", 2.6, 0.45, 0.0, 0.03],
		["scarf.L.0", "scarf.L.2", 0.55, 0.22, 1.6, 0.02],
		["scarf.R.0", "scarf.R.2", 0.55, 0.22, 1.6, 0.02],
	]
	springs.setting_count = chains.size()
	for i in chains.size():
		var c: Array = chains[i]
		springs.set_root_bone_name(i, c[0])
		springs.set_end_bone_name(i, c[1])
		springs.set_extend_end_bone(i, true)
		springs.set_end_bone_direction(i, SkeletonModifier3D.BONE_DIRECTION_FROM_PARENT)
		springs.set_end_bone_length(i, 0.08)
		springs.set_stiffness(i, c[2])
		springs.set_drag(i, c[3])
		springs.set_gravity(i, c[4])
		springs.set_gravity_direction(i, Vector3.DOWN)
		springs.set_radius(i, c[5])
	springs.influence = 0.75


# ---------------------------------------------------------------- control API

func set_drive(steer: float, drift_amount: float, drift_dir: float, look_back: float, delta: float) -> void:
	if tree == null:
		return
	var cur_s: float = tree.get("parameters/steer/blend_position")
	tree.set("parameters/steer/blend_position", lerpf(cur_s, clampf(steer, -1, 1), 1.0 - exp(-delta * 10.0)))
	tree.set("parameters/drift/blend_position", drift_dir)
	var cur_d: float = tree.get("parameters/race_mix/blend_amount")
	tree.set("parameters/race_mix/blend_amount", move_toward(cur_d, drift_amount, delta * 6.0))
	var cur_l: float = tree.get("parameters/look/blend_amount")
	tree.set("parameters/look/blend_amount", move_toward(cur_l, look_back, delta * 5.0))


func set_state(s: String) -> void:
	if tree == null or s == _state:
		return
	_state = s
	tree.set("parameters/state/transition_request", s)
	if s == "victory":
		_victory_timer = 2.9


func fire(shot: String, clip := "") -> void:
	if tree == null:
		return
	if clip != "":
		var bt := tree.tree_root as AnimationNodeBlendTree
		var node := bt.get_node("clip_" + shot) as AnimationNodeAnimation
		if node:
			node.animation = clip
	tree.set("parameters/os_" + shot + "/request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)


func flash(amount: float) -> void:
	if fur_mat:
		fur_mat.set_shader_parameter("flash", amount)


func set_look(yaw: float, pitch := 0.0) -> void:
	if head_look:
		head_look.target_yaw = yaw
		head_look.target_pitch = pitch


func set_wind(v: Vector3) -> void:
	## Apparent wind (m/s, world) pushes the scarf/ears back at speed.
	if springs:
		springs.external_force = v * 0.02


func _process(delta: float) -> void:
	if _victory_timer > 0.0:
		_victory_timer -= delta
		if _victory_timer <= 0.0 and _state == "victory":
			_state = "victory_loop"
			tree.set("parameters/state/transition_request", "victory_loop")
