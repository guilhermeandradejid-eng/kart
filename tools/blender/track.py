"""Baía dos Coqueiros — builds the race track geometry and its gameplay data.

Outputs
  assets/models/track/coconut_bay.glb   visual meshes + collision meshes
  data/tracks/coconut_bay.json          centreline, grid, items, props, AI data

Collision meshes are named with Godot's "-colonly" suffix; the node name
before the suffix is the surface type Godot reads (road, grass, sand, wood,
wall). Visual material names are contracts with shaders/track/*.gdshader:
Road, Planks, Terrain, TunnelRock, Waterfall, Water, Checker, Wood, Rope.
"""

import json
import math
import os

import numpy as np
from scipy.spatial import cKDTree

from tt import core as C
from tt import sdf as S
import track_layout as TL

BOUNDS = (-330.0, -140.0, 260.0, 380.0)   # x0, y0, x1, y1 (Blender)
CELL = 2.5
CURB_W = 1.3
SHOULDER = 5.0          # offroad band between road edge and invisible wall
WALL_H = 3.0
ACROSS = 14             # road segments across the width

RIVER = np.array([(70, 196), (104, 206), (152, 214), (196, 204), (236, 170), (262, 110), (270, 40), (272, -40)], float)
LAGOON = (78, 196, 26.0)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def seg_dist(P, poly):
    """Distance from points P (N,2) to a polyline."""
    d = np.full(len(P), 1e9)
    for a, b in zip(poly[:-1], poly[1:]):
        ab = b - a
        t = np.clip(((P - a) @ ab) / (ab @ ab), 0, 1)
        d = np.minimum(d, np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    return d


class Track:
    def __init__(self):
        self.L = TL.Layout()
        L = self.L
        self.tree = cKDTree(L.pos[:, :2])
        self.gap_mid = L.index_at(L.ramp_s + 12.0)
        self.tags = L.tags

    # ---------------------------------------------------------------- road
    def ramp_lift(self, s_arr):
        """Extra height of the launch kicker before the gap."""
        r0 = self.L.ramp_s - 9.0
        r1 = self.L.ramp_s + 3.0
        t = np.clip((s_arr - r0) / (r1 - r0), 0, 1)
        return 1.7 * t ** 2.2

    def road_point(self, i, o, crown=True):
        L = self.L
        w = L.width[i]
        h = 0.0
        if crown:
            h = 0.04 * (1 - (2 * o / w) ** 2) if abs(o) < w / 2 else 0.0
            if abs(o) > w / 2:
                q = (abs(o) - w / 2) / CURB_W
                h = 0.07 * math.sin(min(q, 1.0) * math.pi * 0.5) if q <= 1.0 else 0.07 - (q - 1.0) * 0.6
        lift = self.ramp_lift(np.array([L.s[i]]))[0]
        return L.pos[i] + L.right[i] * o + L.up[i] * h + np.array([0, 0, lift])

    def build_road(self, m):
        L = self.L
        n = L.n
        offs = []
        # across: skirt, curb outer, curb inner, road..., curb inner, curb outer, skirt
        road_u = np.linspace(-0.5, 0.5, ACROSS + 1)
        verts, uvs, cols = [], [], []
        idx = np.zeros((n, ACROSS + 5), dtype=np.int64)
        curbness = smoothstep(0.006, 0.014, np.abs(L.curv))
        curbness = TL.smooth_closed(curbness, 30)
        for i in range(n):
            w = L.width[i]
            os_ = ([-(w / 2 + CURB_W + 0.6), -(w / 2 + CURB_W)] + list(road_u * w) + [w / 2 + CURB_W, w / 2 + CURB_W + 0.6])
            # insert curb edges exactly at +-w/2 (already the road ends) -> curb band is road_u[0]..skirt
            for j, o in enumerate(os_):
                p = self.road_point(i, o)
                if j in (0, len(os_) - 1):
                    p = p - L.up[i] * 0.45     # skirt dips under the terrain
                idx[i, j] = len(verts)
                verts.append(p)
                # u: 0..1 across the full strip (curbs occupy the outer bands), v in metres/4
                u = (o + (w / 2 + CURB_W)) / (w + 2 * CURB_W)
                uvs.append((u, L.s[i] / 4.0))
                cols.append((curbness[i], w / 20.0, 1.0 if "bridge" in L.tags[i] else 0.0))
        nj = ACROSS + 5
        faces, fmat = [], []
        for i in range(n):
            if "gap" in L.tags[i] or "gap" in L.tags[(i + 1) % n]:
                continue
            i2 = (i + 1) % n
            bridge = "bridge" in L.tags[i]
            for j in range(nj - 1):
                faces.append((idx[i, j], idx[i2, j], idx[i2, j + 1], idx[i, j + 1]))
                fmat.append(1 if bridge else 0)
        V = np.array(verts)
        # quads are wound so that normals face up (i along fwd, j along right)
        F = np.array(faces)[:, ::-1]
        ob = C.mesh_from_arrays("Road", V, F)
        C.set_materials(ob, [m["road"], m["planks"]])
        C.set_face_materials(ob, fmat)
        self._set_uv(ob, np.array(uvs))
        C.set_vertex_colors(ob, np.array(cols))
        C.shade_smooth(ob, True)
        self.road_V, self.road_F, self.road_mat = V, F, np.array(fmat)
        return ob

    def _set_uv(self, ob, uv, name="UVMap"):
        me = ob.data
        lay = me.uv_layers.new(name=name)
        vi = np.empty(len(me.loops), dtype=np.int64)
        me.loops.foreach_get("vertex_index", vi)
        lay.data.foreach_set("uv", uv[vi].astype(np.float32).ravel())

    def road_collision(self):
        """Road + bridge collision (drops the skirts), split by surface."""
        L = self.L
        n = L.n
        out = {}
        for surf, want_bridge in (("road", False), ("wood", True)):
            V, F = [], []
            for i in range(n):
                if "gap" in L.tags[i] or "gap" in L.tags[(i + 1) % n]:
                    continue
                if ("bridge" in L.tags[i]) != want_bridge:
                    continue
                i2 = (i + 1) % n
                a = [self.road_point(i, o) for o in (-(L.width[i] / 2 + CURB_W), 0.0, L.width[i] / 2 + CURB_W)]
                b = [self.road_point(i2, o) for o in (-(L.width[i2] / 2 + CURB_W), 0.0, L.width[i2] / 2 + CURB_W)]
                for k in range(2):
                    base = len(V)
                    V += [a[k], b[k], b[k + 1], a[k + 1]]
                    F.append((base + 3, base + 2, base + 1, base))
            if V:
                out[surf] = C.mesh_from_arrays(f"{surf}-colonly", np.array(V), np.array(F))
        return out

    # ---------------------------------------------------------------- terrain
    def natural_height(self, X, Y):
        P = np.stack([X, Y, np.zeros_like(X)], axis=1)
        # sea to the south, beach band, hills rising north
        south = -12.0
        z = np.where(Y < south, 1.2 - (south - Y) * 0.075, 1.2 + 0.0 * Y)
        hills = 30.0 * smoothstep(30, 300, Y) * (0.7 + 0.3 * smoothstep(-300, 100, X))
        z = z + hills * smoothstep(south, 40, Y)
        z = z + S.fbm(P * np.array([1, 1, 0]), 1 / 60.0, 4, seed=11) * (1.5 + 6.0 * smoothstep(20, 200, Y))
        # headland east: a rise between the start straight and the bridge
        z = z + 5.0 * np.exp(-(((X - 150) / 60) ** 2 + ((Y - 80) / 60) ** 2))
        # tunnel ridge: a rocky spine crossing the track near the tunnel
        i16 = self.L.near_control(16)
        tp = self.L.pos[i16]
        tf = self.L.fwd[i16]
        perp = np.array([-tf[1], tf[0]])
        dd = np.abs((X - tp[0]) * tf[0] + (Y - tp[1]) * tf[1])       # along-track distance
        along_ridge = np.abs((X - tp[0]) * perp[0] + (Y - tp[1]) * perp[1])
        ridge = (tp[2] + 17.0) * np.exp(-(dd / 46.0) ** 2) * np.exp(-(along_ridge / 120.0) ** 2)
        ridge = ridge + S.fbm(P * np.array([1, 1, 0]), 1 / 25.0, 3, seed=31) * 5.0 * np.exp(-(dd / 60.0) ** 2)
        z = np.maximum(z, ridge)
        # river channel and lagoon
        rd = seg_dist(np.stack([X, Y], 1), RIVER)
        z = np.where(rd < 14, np.minimum(z, -1.6 + rd * 0.05), z) * 1.0
        z = z - np.clip(1 - rd / 26.0, 0, 1) ** 2 * np.maximum(z + 1.6, 0) * 0.9
        ld = np.hypot(X - LAGOON[0], Y - LAGOON[1])
        z = np.where(ld < LAGOON[2], np.minimum(z, -1.8), z)
        z = z - np.clip(1 - (ld - LAGOON[2]) / 22.0, 0, 1) ** 2 * np.maximum(z + 1.8, 0)
        # gorge under the jump
        gp = self.L.pos[self.gap_mid]
        gd = np.hypot(X - gp[0], Y - gp[1])
        z = np.where(gd < 30, np.minimum(z, -3.0), z)
        z = z - np.clip(1 - (gd - 30) / 25.0, 0, 1) ** 1.5 * np.maximum(z + 3.0, 0)
        return z

    def build_terrain(self, m):
        L = self.L
        x0, y0, x1, y1 = BOUNDS
        nx = int((x1 - x0) / CELL) + 1
        ny = int((y1 - y0) / CELL) + 1
        xs = np.linspace(x0, x1, nx)
        ys = np.linspace(y0, y1, ny)
        X, Y = np.meshgrid(xs, ys, indexing="xy")
        X = X.ravel()
        Y = Y.ravel()
        Zn = self.natural_height(X, Y)
        d, ii = self.tree.query(np.stack([X, Y], 1))
        # lateral distance from the road edge
        half = L.width[ii] / 2 + CURB_W
        edge = d - half
        road_z = L.pos[ii, 2] + self.ramp_lift(L.s[ii]) * 0
        # bank: height of the road surface at that lateral position
        rel = np.stack([X - L.pos[ii, 0], Y - L.pos[ii, 1]], 1)
        lat = np.einsum("ij,ij->i", rel, L.right[ii, :2] / np.linalg.norm(L.right[ii, :2], axis=1, keepdims=True))
        slope = L.right[ii, 2] / np.maximum(np.linalg.norm(L.right[ii, :2], axis=1), 1e-6)
        road_here = road_z + np.clip(lat, -half, half) * slope - 0.18
        free = np.array([("gap" in L.tags[k]) or ("bridge" in L.tags[k]) for k in ii])
        tunnel = np.array(["tunnel" in L.tags[k] for k in ii])
        w = smoothstep(0.0, 26.0, edge)
        w = np.where(free, 1.0, w)
        Z = road_here * (1 - w) + Zn * w
        # never let terrain poke through the road (except in tunnels/bridges/gap)
        Z = np.where((edge < 1.0) & ~free & ~tunnel, np.minimum(Z, road_here), Z)
        # bridge / gap: the ground must stay well below the deck on both banks
        bridge = np.array(["bridge" in L.tags[k] for k in ii])
        depth = np.where(bridge, 3.0, 9.0)
        near = free & (edge < 14.0)
        Z = np.where(near, np.minimum(Z, road_here - depth * (1.0 - smoothstep(5.0, 14.0, edge))), Z)
        # tunnel: keep the hill above the tube
        Z = np.where(tunnel & (edge < 12), np.maximum(Z, road_z + 9.5 + edge * 0.2), Z)
        # colour + surface
        P3 = np.stack([X, Y, Z], 1)
        n1 = S.fbm(P3 * np.array([1, 1, 0]), 1 / 14.0, 3, seed=3)
        n2 = S.fbm(P3 * np.array([1, 1, 0]), 1 / 45.0, 3, seed=9)
        sand_w = smoothstep(4.2, 2.4, Z + n2 * 0.8) * smoothstep(90, 50, Y)
        sand_w = np.maximum(sand_w, smoothstep(1.2, 0.2, Z))  # every shore is sandy
        grass = np.array(S.hexrgb("#62b23a"))
        grass2 = np.array(S.hexrgb("#8acc45"))
        dark = np.array(S.hexrgb("#3f8f2c"))
        sand = np.array(S.hexrgb("#f0d49a"))
        wet = np.array(S.hexrgb("#c9a86c"))
        dirt = np.array(S.hexrgb("#b07c4f"))
        col = grass * (0.5 + 0.5 * n1[:, None]) + grass2 * (0.5 - 0.5 * n1[:, None])
        col = col * (1 - smoothstep(0.1, 0.6, n2)[:, None]) + dark * smoothstep(0.1, 0.6, n2)[:, None]
        sandc = sand * (1 - smoothstep(0.9, 0.1, Z)[:, None]) + wet * smoothstep(0.9, 0.1, Z)[:, None]
        col = col * (1 - sand_w[:, None]) + sandc * sand_w[:, None]
        shoulder = smoothstep(4.0, 0.5, edge) * (1 - sand_w) * (1 - free)
        col = col * (1 - shoulder[:, None] * 0.8) + dirt * (shoulder[:, None] * 0.8)
        # faces
        I = np.arange(nx * ny).reshape(ny, nx)
        a = I[:-1, :-1].ravel()
        b = I[:-1, 1:].ravel()
        c = I[1:, 1:].ravel()
        dd_ = I[1:, :-1].ravel()
        F = np.stack([a, b, c, dd_], 1)
        V = np.stack([X, Y, Z], 1)
        # rock on steep slopes (vertex slope from grid gradient)
        Zg = Z.reshape(ny, nx)
        gy, gx = np.gradient(Zg, CELL)
        steep = smoothstep(0.7, 1.3, np.hypot(gx, gy)).ravel()
        rock = np.array(S.hexrgb("#9a8a78"))
        col = col * (1 - steep[:, None]) + rock * steep[:, None]
        ob = C.mesh_from_arrays("Terrain", V, F)
        C.set_materials(ob, [m["terrain"]])
        # alpha channel carries the sand weight (shader uses it for detail textures)
        C.set_vertex_colors(ob, np.concatenate([col, sand_w[:, None] * (1 - steep[:, None])], 1))
        uv = np.stack([X / 8.0, Y / 8.0], 1)
        self._set_uv(ob, uv)
        C.shade_smooth(ob, True)
        self.terrain = (V, F, sand_w, nx, ny)
        self.edge_dist = edge
        return ob

    def terrain_collision(self):
        V, F, sand_w, nx, ny = self.terrain
        fs = sand_w[F].mean(axis=1)
        # only collide with terrain that a kart can actually reach (+ margins)
        cz = V[F].mean(axis=1)
        d, _ = self.tree.query(cz[:, :2])
        keep = d < (self.L.width.max() / 2 + CURB_W + SHOULDER + 30)
        out = {}
        for surf, sel in (("sand", fs >= 0.5), ("grass", fs < 0.5)):
            f = F[keep & sel]
            if len(f):
                used = np.unique(f)
                remap = -np.ones(len(V), dtype=np.int64)
                remap[used] = np.arange(len(used))
                out[surf] = C.mesh_from_arrays(f"{surf}-colonly", V[used], remap[f])
        return out

    # ---------------------------------------------------------------- walls
    def walls(self):
        L = self.L
        n = L.n
        V, F = [], []
        for side in (-1, 1):
            ring = []
            for i in range(0, n, 2):
                w = L.width[i] / 2 + CURB_W + SHOULDER
                if "tunnel" in L.tags[i]:
                    w = L.width[i] / 2 + CURB_W + 1.2
                if "bridge" in L.tags[i]:
                    w = L.width[i] / 2 + CURB_W + 0.6
                p = L.pos[i] + L.right[i] * 0 + np.array([L.right[i, 0], L.right[i, 1], 0]) / np.linalg.norm(L.right[i, :2]) * w * side
                p = p.copy()
                p[2] = L.pos[i, 2] - 4.0
                ring.append(p)
            m_ = len(ring)
            base = len(V)
            for p in ring:
                V.append(p)
                V.append(p + np.array([0, 0, 4.0 + WALL_H + 3.0]))
            for k in range(m_):
                a = base + 2 * k
                b = base + 2 * ((k + 1) % m_)
                F.append((a, b, b + 1, a + 1) if side > 0 else (a + 1, b + 1, b, a))
        return C.mesh_from_arrays("wall-colonly", np.array(V), np.array(F))

    # ---------------------------------------------------------------- set pieces
    def build_tunnel(self, m):
        L = self.L
        idx = [i for i in range(L.n) if "tunnel" in L.tags[i]]
        prof = []
        half = L.width[idx[0]] / 2 + CURB_W + 1.4
        for k in range(15):
            a = math.pi * k / 14
            prof.append((-math.cos(a) * half * 1.02, 5.2 * math.sin(a) + 3.2 * (1 - abs(math.cos(a)) ** 6)))
        prof = [(-half, -0.6)] + prof + [(half, -0.6)]
        V, F, cols = [], [], []
        rows = []
        for i in idx:
            row = []
            for (o, h) in prof:
                p = L.pos[i] + np.array([L.right[i, 0], L.right[i, 1], 0]) * o + np.array([0, 0, h])
                row.append(len(V))
                V.append(p)
            rows.append(row)
        for r in range(len(rows) - 1):
            for k in range(len(prof) - 1):
                F.append((rows[r][k], rows[r][k + 1], rows[r + 1][k + 1], rows[r + 1][k]))
        V = np.array(V)
        # rocky displacement, keep the floor edge anchored
        nrm = np.zeros_like(V)
        noise = S.fbm(V, 1 / 3.0, 3, seed=21)
        V = V + np.array([0, 0, 1.0]) * noise[:, None] * 0.35
        cols = np.array(S.hexrgb("#8d7f70")) * (0.75 + 0.25 * S.fbm(V, 1 / 2.0, 2, seed=4))[:, None]
        ob = C.mesh_from_arrays("Tunnel", V, np.array(F))
        C.set_materials(ob, [m["tunnel"]])
        C.set_vertex_colors(ob, cols)
        C.shade_smooth(ob, True)
        del nrm
        self.tunnel_idx = idx
        return ob

    def build_bridge(self, m):
        """Posts, rope rails and pillars. The deck is the Planks part of the road."""
        L = self.L
        idx = [i for i in range(L.n) if "bridge" in L.tags[i]]
        objs = []
        posts = []
        for side in (-1, 1):
            tops = []
            for k, i in enumerate(idx[::4]):
                o = side * (L.width[i] / 2 + CURB_W - 0.25)
                base = self.road_point(i, o)
                top = base + np.array([0, 0, 1.25])
                posts.append(C.cylinder("post", r=0.13, depth=1.5, loc=tuple(base + np.array([0, 0, 0.6])), mat=m["wood"]))
                tops.append(top)
            for a, b in zip(tops[:-1], tops[1:]):
                mid = (a + b) / 2 - np.array([0, 0, 0.25])
                objs.append(C.tube("rope", [a, (a + mid) / 2 - np.array([0, 0, 0.08]), mid, (mid + b) / 2 - np.array([0, 0, 0.08]), b],
                                   radius=0.045, mat=m["rope"]))
        for i in idx[6::12]:
            for side in (-1, 1):
                p = self.road_point(i, side * (L.width[i] / 2 - 1.5))
                h = p[2] + 3.0
                objs.append(C.cylinder("pillar", r=0.45, depth=h, loc=(p[0], p[1], p[2] - h / 2 - 0.2), mat=m["wood"], bevel=0.05))
        # deck beams under the planks
        for i in idx[::3]:
            a = self.road_point(i, -(L.width[i] / 2 + CURB_W)) - np.array([0, 0, 0.25])
            b = self.road_point(i, L.width[i] / 2 + CURB_W) - np.array([0, 0, 0.25])
            objs.append(C.tube("beam", [a, b], radius=0.16, mat=m["wood"]))
        ob = C.join(posts + objs, "Bridge")
        return ob

    def build_waterfall(self, m):
        """Curved falling sheet into the gorge + foam ring (UV v runs downward)."""
        L = self.L
        g = self.gap_mid
        c = L.pos[g]
        side = -np.array([L.right[g, 0], L.right[g, 1], 0])
        side /= np.linalg.norm(side)
        top = c + side * 26 + np.array([0, 0, 9.0])
        fwd = np.array([L.fwd[g, 0], L.fwd[g, 1], 0])
        V, F, uv = [], [], []
        rows, cols_ = 16, 12
        for r in range(rows + 1):
            t = r / rows
            for k in range(cols_ + 1):
                u = k / cols_ - 0.5
                p = top + fwd * u * 14 - side * (3.0 * t * t + 1.0 * t) + np.array([0, 0, -12.5 * t])
                p = p + side * 0.6 * math.sin(u * 5)
                V.append(p)
                uv.append((k / cols_, t * 3.0))
        for r in range(rows):
            for k in range(cols_):
                a = r * (cols_ + 1) + k
                F.append((a, a + 1, a + cols_ + 2, a + cols_ + 1))
        ob = C.mesh_from_arrays("Waterfall", np.array(V), np.array(F))
        C.set_materials(ob, [m["waterfall"]])
        self._set_uv(ob, np.array(uv))
        C.shade_smooth(ob, True)
        self.waterfall_base = top - side * 4 + np.array([0, 0, -12.5])
        return ob

    def build_water(self, m):
        x0, y0, x1, y1 = BOUNDS
        pad = 600
        V = np.array([(x0 - pad, y0 - pad, 0), (x1 + pad, y0 - pad, 0), (x1 + pad, y1 + pad, 0), (x0 - pad, y1 + pad, 0)], float)
        # a subdivided grid so vertex waves and depth fade look right near shore
        nx, ny = 60, 50
        xs = np.linspace(x0 - pad, x1 + pad, nx)
        ys = np.linspace(y0 - pad, y1 + pad, ny)
        X, Y = np.meshgrid(xs, ys, indexing="xy")
        V = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], 1)
        I = np.arange(nx * ny).reshape(ny, nx)
        F = np.stack([I[:-1, :-1].ravel(), I[:-1, 1:].ravel(), I[1:, 1:].ravel(), I[1:, :-1].ravel()], 1)
        ob = C.mesh_from_arrays("Water", V, F)
        C.set_materials(ob, [m["water"]])
        self._set_uv(ob, V[:, :2] / 20.0)
        return ob

    def build_start(self, m):
        L = self.L
        i = L.index_at(L.start_s())
        w = L.width[i]
        V, F, uv = [], [], []
        for k, s_off in enumerate((-1.2, 1.2)):
            j = L.index_at(L.start_s() + s_off)
            for o in (-w / 2, w / 2):
                V.append(self.road_point(j, o) + L.up[j] * 0.015)
                uv.append(((o + w / 2) / w * 10, k))
        F = [(0, 2, 3, 1)]
        ob = C.mesh_from_arrays("StartLine", np.array(V), np.array(F))
        C.set_materials(ob, [m["checker"]])
        self._set_uv(ob, np.array(uv))
        return ob

    # ---------------------------------------------------------------- gameplay data
    def gameplay(self):
        L = self.L
        G = TL.to_godot
        out = {"name": "Baía dos Coqueiros", "id": "coconut_bay", "length": L.length, "laps": 3,
               "water_level": TL.WATER_LEVEL}
        step = 2
        samples = []
        for i in range(0, L.n, step):
            samples.append({"p": G(L.pos[i] + np.array([0, 0, self.ramp_lift(np.array([L.s[i]]))[0]])),
                            "f": G(L.fwd[i]), "r": G(L.right[i]), "u": G(L.up[i]),
                            "w": round(float(L.width[i]), 3), "s": round(float(L.s[i]), 3),
                            "c": round(float(L.curv[i]), 5), "t": sorted(L.tags[i])})
        out["samples"] = samples
        s0 = L.start_s()
        out["start_s"] = s0

        def basis(i, lateral=0.0, back=0.0, lift=0.0):
            p = self.road_point(i, lateral) + L.up[i] * lift
            return {"p": G(p), "x": G(L.right[i]), "y": G(L.up[i]), "z": G(-L.fwd[i])}

        grid = []
        for k in range(8):
            row, col = divmod(k, 2)
            s = s0 - 5.0 - row * 6.5 - col * 3.0
            i = L.index_at(s)
            lat = (-1 if col == 0 else 1) * L.width[i] * 0.2
            grid.append(basis(i, lat, lift=0.6))
        out["grid"] = grid
        # checkpoints (fractions of a lap) used for lap validation
        out["checkpoints"] = [round(L.length * f, 2) for f in (0.25, 0.5, 0.75)]
        # item box rows
        rows = []
        for s in (s0 + 150, s0 + 520, s0 + 860, s0 + 1080):
            i = L.index_at(s)
            n = 5 if L.width[i] >= 16 else 4
            for k in range(n):
                lat = (k - (n - 1) / 2) * (L.width[i] / (n + 0.6))
                rows.append(basis(i, lat, lift=1.25))
        out["item_boxes"] = rows
        # boost pads: straight after T1, on the bridge exit, before the ramp, final straight
        pads = []
        for s, lat in ((s0 + 95, 0.25), (s0 + 480, -0.2), (L.ramp_s - 22, 0.0), (s0 - 120, -0.25)):
            i = L.index_at(s)
            pads.append(basis(i, lat * L.width[i] / 2, lift=0.03))
        out["boost_pads"] = pads
        out["ramp"] = basis(L.index_at(L.ramp_s), 0.0)
        out["ramp"]["s"] = L.ramp_s
        # golden seashells: lines on the racing line in a few sections
        shells = []
        for s_start, n, lat0, lat1 in ((s0 + 40, 6, -0.3, 0.3), (s0 + 300, 5, 0.35, 0.35), (s0 + 640, 6, -0.2, 0.2),
                                        (s0 + 1000, 5, 0.3, -0.3), (L.ramp_s + 9, 3, 0.0, 0.0)):
            for k in range(n):
                s = s_start + k * 5.0
                i = L.index_at(s)
                lat = (lat0 + (lat1 - lat0) * k / max(1, n - 1)) * L.width[i] / 2
                lift = 1.0 + (3.2 * math.sin(math.pi * (k + 0.5) / n) if s_start > L.ramp_s else 0.0)
                shells.append(basis(i, lat, lift=lift))
        out["shells"] = shells
        # tunnel lamps
        lamps = []
        for i in self.tunnel_idx[4::10]:
            for side in (-1, 1):
                p = L.pos[i] + np.array([L.right[i, 0], L.right[i, 1], 0]) * side * (L.width[i] / 2 + CURB_W + 0.9) + np.array([0, 0, 3.4])
                lamps.append({"p": G(p)})
        out["tunnel_lights"] = lamps
        out["waterfall_base"] = G(self.waterfall_base)
        out["decor"], out["scatter"] = self.decor()
        return out

    def decor(self):
        L = self.L
        G = TL.to_godot
        rng = np.random.default_rng(7)
        items = []
        V, F, sand_w, nx, ny = self.terrain
        Z = V[:, 2]

        def ground(x, y):
            gx = int(round((x - BOUNDS[0]) / CELL))
            gy = int(round((y - BOUNDS[1]) / CELL))
            gx = min(max(gx, 0), nx - 1)
            gy = min(max(gy, 0), ny - 1)
            k = gy * nx + gx
            return Z[k], sand_w[k]

        def add(prop, x, y, yaw=None, s=1.0, z=None, clear=4.0):
            d, i = self.tree.query((x, y))
            if d < L.width[i] / 2 + CURB_W + clear:
                return False
            gz, sw = ground(x, y)
            if z is None:
                z = gz
            if z < 0.2 and prop not in ("buoy", "boat"):
                return False
            items.append({"prop": prop, "p": G((x, y, z)), "yaw": float(yaw if yaw is not None else rng.uniform(0, 360)),
                          "s": float(s)})
            return True

        def along(prop, s_from, s_to, every, side, dist, jitter=1.0, scale=(1, 1), yaw_mode="face", clear=3.0):
            s = s_from
            while s < s_to:
                i = L.index_at(s)
                if "gap" in L.tags[i]:
                    s += every
                    continue
                r2 = L.right[i, :2] / np.linalg.norm(L.right[i, :2])
                off = L.width[i] / 2 + CURB_W + dist + rng.uniform(-jitter, jitter)
                x, y = L.pos[i, :2] + r2 * off * side
                f = L.fwd[i]
                yaw = math.degrees(math.atan2(f[0], f[1]))  # Blender yaw facing along track
                if yaw_mode == "face":
                    yaw = yaw + (90 if side > 0 else -90)
                elif yaw_mode == "random":
                    yaw = None
                add(prop, x, y, yaw, rng.uniform(*scale), clear=clear)
                s += every * rng.uniform(0.8, 1.2)

        s0 = L.start_s()
        Ln = L.length
        # --- start straight: grandstands (sea side is -right), arch, flags, banners
        i = L.index_at(s0)
        r2 = L.right[i, :2] / np.linalg.norm(L.right[i, :2])
        for k, off in enumerate((-40, -10, 20)):
            j = L.index_at(s0 + off)
            p = L.pos[j, :2] - r2 * (L.width[j] / 2 + CURB_W + SHOULDER + 3.0)
            f = L.fwd[j]
            add("grandstand", p[0], p[1], math.degrees(math.atan2(f[0], f[1])) + 180 + 90, 1.0, clear=2)
        add_arch = self.road_point(i, 0)
        items.append({"prop": "start_arch", "p": G(add_arch - np.array([0, 0, 0.1])),
                      "yaw": float(math.degrees(math.atan2(L.fwd[i, 0], L.fwd[i, 1]))), "s": 1.0})
        along("feather_banner", s0 - 90, s0 + 80, 12, -1, 1.8, 0.3, yaw_mode="face", clear=1.5)
        along("flag_pole", s0 - 60, s0 + 60, 18, 1, 2.5, 0.3, clear=1.5)
        along("barrier", s0 - 150, s0 + 110, 2.1, 1, 0.9, 0.0, yaw_mode="along", clear=0.5)
        # --- beach life on the sea side of the straight
        for k in range(40):
            s = s0 - 180 + k * 8.5
            j = L.index_at(s)
            p = L.pos[j, :2] + np.array([0, -1]) * rng.uniform(22, 48)
            prop = rng.choice(["umbrella", "umbrella", "beach_chair", "palm_a", "palm_b", "beach_ball", "surfboard_rack"])
            add(prop, p[0], p[1], None, rng.uniform(0.9, 1.15), clear=6)
        for x in (-200, -120, -20, 60):
            add("beach_hut", x + rng.uniform(-8, 8), -30 + rng.uniform(-3, 3), 0.0, 1.0, clear=8)
        add("lifeguard_tower", -95, -40, 0.0, 1.0)
        for k in range(10):
            add("buoy", rng.uniform(-300, 200), rng.uniform(-110, -60), None, 1.0, z=0.0, clear=0)
        for k in range(4):
            add("boat", rng.uniform(-260, 150), rng.uniform(-130, -85), None, 1.0, z=0.0, clear=0)
        # --- palms line the whole beach section and the headland
        along("palm_a", s0 - 250, s0 + 260, 16, 1, 7.0, 3.0, (0.85, 1.2), "random", clear=5)
        along("palm_b", s0 - 240, s0 + 260, 19, -1, 9.0, 3.0, (0.85, 1.25), "random", clear=6)
        along("palm_c", s0 + 150, s0 + 430, 15, 1, 8.0, 3.5, (0.9, 1.2), "random", clear=5)
        along("palm_a", s0 + 150, s0 + 430, 17, -1, 8.0, 3.5, (0.9, 1.2), "random", clear=5)
        # corner furniture
        for s_c in np.linspace(0, Ln, 120, endpoint=False):
            i = L.index_at(s_c)
            if abs(L.curv[i]) > 0.02 and "tunnel" not in L.tags[i] and "bridge" not in L.tags[i]:
                side = -1 if L.curv[i] > 0 else 1   # outside of the turn
                along("tire_stack", s_c, s_c + 3, 3, side, SHOULDER + 0.6, 0.1, (0.95, 1.05), "random", clear=1)
        for s_c in np.linspace(0, Ln, 60, endpoint=False):
            i = L.index_at(s_c)
            if abs(L.curv[i]) > 0.026 and "tunnel" not in L.tags[i]:
                side = -1 if L.curv[i] > 0 else 1
                along("sign_chevron", s_c, s_c + 1, 1, side, SHOULDER - 0.8, 0.0, yaw_mode="face", clear=1)
        # --- jungle: dense vegetation, rocks and fences on the climb and descent
        jungle = [(s0 + 500, s0 + 700), (s0 + 820, s0 + 1100)]
        for a, b in jungle:
            for side in (-1, 1):
                along("jungle_tree", a, b, 22, side, 14, 5, (0.8, 1.3), "random", clear=8)
                along("bush_a", a, b, 9, side, 7.5, 2.5, (0.8, 1.3), "random", clear=5)
                along("banana_plant", a, b, 17, side, 9.5, 2.0, (0.8, 1.2), "random", clear=5)
                along("fern", a, b, 7, side, 6.2, 1.2, (0.8, 1.2), "random", clear=5)
                along("rock_a", a, b, 31, side, 11, 4, (0.8, 1.6), "random", clear=6)
                along("bamboo_fence", a, b, 3.05, side, SHOULDER + 0.3, 0.0, (1, 1), "along", clear=1)
        for s_c in (s0 + 430, s0 + 560, s0 + 900, s0 + 1010):
            along("tiki_torch", s_c, s_c + 60, 12, 1, 2.2, 0.2, clear=1.5)
            along("tiki_torch", s_c, s_c + 60, 12, -1, 2.2, 0.2, clear=1.5)
        # tunnel portals + ridge rocks
        for s_edge, facing in ((self.L.features["tunnel"][0][0] - 2, 0), (self.L.features["tunnel"][0][1] + 2, 180)):
            i = L.index_at(s_edge)
            f = L.fwd[i]
            yaw = math.degrees(math.atan2(f[0], f[1])) + facing
            p = self.road_point(i, 0) - np.array([0, 0, 0.6])
            items.append({"prop": "rock_arch", "p": G(p), "yaw": float(yaw), "s": 1.05})
            for side in (-1, 1):
                r2 = L.right[i, :2] / np.linalg.norm(L.right[i, :2])
                q = L.pos[i, :2] + r2 * side * 24
                add("cliff_a" if side > 0 else "cliff_b", q[0], q[1], yaw, 1.0, clear=2)
        # gorge cliffs
        g = self.gap_mid
        for ang in range(0, 360, 45):
            q = L.pos[g, :2] + 34 * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
            add("cliff_b" if ang % 90 else "cliff_a", q[0], q[1], ang + 90, rng.uniform(0.8, 1.1), clear=4)
        # hills: sprinkle palms/trees/rocks in the open areas
        for k in range(700):
            x = rng.uniform(BOUNDS[0] + 10, BOUNDS[2] - 10)
            y = rng.uniform(-10, BOUNDS[3] - 10)
            gz, sw = ground(x, y)
            if gz < 0.8:
                continue
            if sw > 0.5:
                prop = rng.choice(["palm_a", "palm_b", "palm_c", "bush_b", "rock_flat"])
            else:
                prop = rng.choice(["jungle_tree", "jungle_tree", "palm_c", "bush_a", "bush_b", "banana_plant", "rock_b", "rock_c", "flowers"])
            add(prop, x, y, None, rng.uniform(0.8, 1.35), clear=16)
        # scatter (instanced with MultiMesh in Godot)
        scatter = {"grass_tuft": [], "flowers": []}
        for k in range(26000):
            x = rng.uniform(BOUNDS[0], BOUNDS[2])
            y = rng.uniform(-5, BOUNDS[3])
            gz, sw = ground(x, y)
            if gz < 1.0 or sw > 0.4:
                continue
            d, i = self.tree.query((x, y))
            if d < L.width[i] / 2 + CURB_W + 1.0 or d > 120:
                continue
            key = "flowers" if rng.random() < 0.06 else "grass_tuft"
            scatter[key].append([round(v, 2) for v in G((x, y, gz))] + [round(float(rng.uniform(0, 6.283)), 2),
                                                                         round(float(rng.uniform(0.7, 1.4)), 2)])
        return items, scatter


def materials():
    return dict(
        road=C.material("Road", "#5d5a60", rough=0.8),
        planks=C.material("Planks", "#a0703f", rough=0.7),
        terrain=C.material("Terrain", "#ffffff", rough=0.95, use_vcol=True),
        tunnel=C.material("TunnelRock", "#ffffff", rough=0.9, use_vcol=True),
        waterfall=C.material("Waterfall", "#bff0ff", rough=0.1, alpha=0.8),
        water=C.material("Water", "#3fc6d8", rough=0.05, alpha=0.8),
        checker=C.material("Checker", "#ffffff", rough=0.6),
        wood=C.material("Wood", "#8a5a33", rough=0.8),
        rope=C.material("Rope", "#d8c08a", rough=0.9),
    )


def build(out_root, preview=None):
    C.reset()
    m = materials()
    T = Track()
    root = C.empty("CoconutBay", (0, 0, 0))
    vis = C.empty("Visual", (0, 0, 0), parent=root)
    col = C.empty("Collision", (0, 0, 0), parent=root)
    parts = [T.build_road(m), T.build_terrain(m), T.build_tunnel(m), T.build_bridge(m), T.build_waterfall(m),
             T.build_water(m), T.build_start(m)]
    for o in parts:
        o.parent = vis
    cols = list(T.road_collision().values()) + list(T.terrain_collision().values()) + [T.walls()]
    for o in cols:
        o.parent = col
    C.export_glb(os.path.join(out_root, "track", "coconut_bay.glb"), [root])
    data = T.gameplay()
    root_dir = os.path.abspath(os.path.join(out_root, "..", ".."))
    path = os.path.join(root_dir, "data", "tracks", "coconut_bay.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print("wrote", path, "decor", len(data["decor"]), "grass", len(data["scatter"]["grass_tuft"]))
    if preview:
        from tt import render as R
        import bpy
        R.camera((-40, 120, 0), 520, -20, 55, lens=35)
        sun = bpy.data.lights.new("Sun", "SUN")
        so = bpy.data.objects.new("Sun", sun)
        bpy.context.scene.collection.objects.link(so)
        so.rotation_euler = (math.radians(40), 0, math.radians(30))
        sun.energy = 4
        for o in cols:
            o.hide_render = True
        R._world("#9fd2ff", 1.0)
        R.render(preview + "_overview.png", (1100, 800), samples=12)
