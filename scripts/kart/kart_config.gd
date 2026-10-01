class_name KartConfig
extends Resource
## A kart build: one part per slot plus the paint job. Serialisable so the
## garage can save it and future unlocks (new wheels, bodies, decals, horns...)
## only need a new entry in KartParts.CATALOG.

@export var body := "classic"
@export var wheels := "standard"
@export var wing := "classic"
@export var engine := "single"
@export var color_primary := Color("e0342c")
@export var color_secondary := Color("ffc93c")
@export var color_rim := Color("ffd23f")
@export var pattern := 1           # livery pattern index (see shaders/kart_paint.gdshader)
@export var number := 7
@export var driver := "guara"
@export var driver_variant := 0    # fur/outfit colourway


func slot(s: String) -> String:
	return get(s)


func set_slot(s: String, id: String) -> void:
	set(s, id)


func duplicate_config() -> KartConfig:
	return KartConfig.from_dict(to_dict())


func to_dict() -> Dictionary:
	return {
		"body": body, "wheels": wheels, "wing": wing, "engine": engine,
		"color_primary": color_primary.to_html(false), "color_secondary": color_secondary.to_html(false),
		"color_rim": color_rim.to_html(false), "pattern": pattern, "number": number,
		"driver": driver, "driver_variant": driver_variant,
	}


static func from_dict(d: Dictionary) -> KartConfig:
	var c := KartConfig.new()
	for k in ["body", "wheels", "wing", "engine", "driver"]:
		if d.has(k) and KartParts.has_part(k, d[k]) or k == "driver" and d.has(k):
			c.set(k, d[k])
	for k in ["color_primary", "color_secondary", "color_rim"]:
		if d.has(k):
			c.set(k, Color(d[k]))
	c.pattern = int(d.get("pattern", c.pattern))
	c.number = int(d.get("number", c.number))
	c.driver_variant = int(d.get("driver_variant", 0))
	return c


static func random(rng: RandomNumberGenerator) -> KartConfig:
	var c := KartConfig.new()
	for s in KartParts.SLOTS:
		var ids: Array = KartParts.CATALOG[s].keys()
		c.set(s, ids[rng.randi() % ids.size()])
	var pal: Array = KartParts.PALETTES[rng.randi() % KartParts.PALETTES.size()]
	c.color_primary = pal[0]
	c.color_secondary = pal[1]
	c.color_rim = pal[2]
	c.pattern = rng.randi() % KartParts.PATTERNS.size()
	c.number = rng.randi_range(1, 99)
	return c
