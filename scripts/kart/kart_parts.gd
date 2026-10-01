class_name KartParts
extends RefCounted
## Catalogue of every customisable kart part. Adding content = adding an entry
## (and its .glb from tools/blender/kart_parts.py). Stats are deltas on a 0..6
## scale around a neutral kart (MK8-style: parts trade stats against each other).

const SLOTS := ["body", "wheels", "wing", "engine"]
const SLOT_NAMES := {"body": "Carroceria", "wheels": "Rodas", "wing": "Aerofólio", "engine": "Motor"}
const STAT_NAMES := {
	"speed": "Velocidade", "accel": "Aceleração", "weight": "Peso",
	"handling": "Manobra", "traction": "Tração", "turbo": "Mini-turbo",
}
const BASE_STATS := {"speed": 3.0, "accel": 3.0, "weight": 3.0, "handling": 3.0, "traction": 3.0, "turbo": 3.0}

const CATALOG := {
	"body": {
		"classic": {"name": "Clássico", "scene": "res://assets/models/karts/bodies/classic.glb",
			"stats": {"speed": 0.3, "accel": 0.3, "handling": 0.3, "turbo": 0.3}},
		"bolt": {"name": "Raio", "scene": "res://assets/models/karts/bodies/bolt.glb",
			"stats": {"speed": 1.0, "accel": -0.4, "handling": 0.4, "weight": -0.3, "traction": -0.5, "turbo": 0.4}},
		"buggy": {"name": "Buggy", "scene": "res://assets/models/karts/bodies/buggy.glb",
			"stats": {"speed": -0.3, "accel": 0.4, "weight": 1.2, "handling": -0.3, "traction": 1.3}},
	},
	"wheels": {
		"standard": {"name": "Padrão", "scene": "res://assets/models/karts/wheels/standard.glb",
			"front_r": 0.20, "rear_r": 0.24, "stats": {}},
		"slick": {"name": "Slick", "scene": "res://assets/models/karts/wheels/slick.glb",
			"front_r": 0.19, "rear_r": 0.23, "stats": {"speed": 0.6, "handling": 0.3, "traction": -0.9}},
		"monster": {"name": "Monstro", "scene": "res://assets/models/karts/wheels/monster.glb",
			"front_r": 0.27, "rear_r": 0.30, "stats": {"speed": -0.5, "accel": -0.2, "weight": 0.9, "traction": 1.6, "handling": -0.4}},
		"mini": {"name": "Rolimã", "scene": "res://assets/models/karts/wheels/mini.glb",
			"front_r": 0.16, "rear_r": 0.18, "stats": {"accel": 1.2, "speed": -0.4, "weight": -0.6, "turbo": 0.9, "handling": 0.4}},
	},
	"wing": {
		"classic": {"name": "Asa Clássica", "scene": "res://assets/models/karts/wings/classic.glb",
			"stats": {"handling": 0.3, "turbo": 0.3}},
		"twin": {"name": "Asa Dupla", "scene": "res://assets/models/karts/wings/twin.glb",
			"stats": {"speed": 0.2, "handling": 0.5, "accel": -0.2}},
		"duck": {"name": "Rabo de Pato", "scene": "res://assets/models/karts/wings/duck.glb",
			"stats": {"accel": 0.4, "weight": -0.2}},
	},
	"engine": {
		"single": {"name": "Monocilíndrico", "scene": "res://assets/models/karts/engines/single.glb",
			"stats": {"accel": 0.3}, "pitch": 1.08},
		"twin": {"name": "Bicilíndrico", "scene": "res://assets/models/karts/engines/twin.glb",
			"stats": {"speed": 0.5, "accel": -0.2, "weight": 0.3}, "pitch": 0.92},
	},
}

const CHASSIS := "res://assets/models/karts/chassis/standard.glb"
const PATTERNS := ["Liso", "Faixa Central", "Faixas Duplas", "Chamas", "Xadrez", "Onça"]
const PALETTES := [
	[Color("e0342c"), Color("ffc93c"), Color("ffd23f")],
	[Color("2f6fe0"), Color("f2f2f2"), Color("e0342c")],
	[Color("24b04a"), Color("2f6fe0"), Color("f2f2f2")],
	[Color("ff8a1f"), Color("2a2a33"), Color("ff8a1f")],
	[Color("9b4be0"), Color("ff6fb5"), Color("f2f2f2")],
	[Color("1fb7c9"), Color("ffe14d"), Color("1f9e4a")],
	[Color("f2f2f2"), Color("e0342c"), Color("2a2a33")],
	[Color("ffd23f"), Color("1f9e4a"), Color("2f6fe0")],
	[Color("2a2a33"), Color("ff3b6b"), Color("ff3b6b")],
	[Color("ff5fa2"), Color("5ee0ff"), Color("ffffff")],
]


static func has_part(slot: String, id: String) -> bool:
	return CATALOG.has(slot) and CATALOG[slot].has(id)


static func part(slot: String, id: String) -> Dictionary:
	return CATALOG[slot].get(id, CATALOG[slot].values()[0])


## Final stats (0..6) for a build.
static func stats_for(cfg: KartConfig) -> Dictionary:
	var s := BASE_STATS.duplicate()
	for slot in SLOTS:
		var d: Dictionary = part(slot, cfg.get(slot)).stats
		for k in d:
			s[k] = clampf(s[k] + d[k], 0.5, 6.0)
	return s


## Physical tuning derived from stats (consumed by Kart).
static func tuning_for(cfg: KartConfig) -> Dictionary:
	var s := stats_for(cfg)
	return {
		"max_speed": 25.5 + s.speed * 1.05,        # m/s (~100-115 km/h)
		"accel_time": 3.1 - s.accel * 0.28,        # seconds to ~90% of top speed
		"turn_rate": 1.75 + s.handling * 0.11,     # rad/s at mid speed
		"weight": 0.8 + s.weight * 0.14,
		"offroad": 0.50 + s.traction * 0.045,      # speed multiplier on grass/sand
		"grip": 7.5 + s.traction * 0.7,            # lateral velocity damping
		"turbo": 0.85 + s.turbo * 0.07,            # mini-turbo duration multiplier
	}
