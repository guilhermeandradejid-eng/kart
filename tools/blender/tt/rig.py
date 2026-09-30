"""Armature building, skinning and clip baking (see anim.py for authoring)."""

import math

import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from . import anim as A
from . import core as C


def build_armature(name, bones):
    """bones: list of (name, head, tail, parent, deform=True).
    Rolls: bones mostly along Z get their local Z aligned to world -Y,
    bones along Y get local Z aligned to world +Z; sideways bones -Y."""
    data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    C.link(arm)
    C.activate(arm)
    bpy.ops.object.mode_set(mode="EDIT")
    for spec in bones:
        bn, head, tail, parent = spec[:4]
        deform = spec[4] if len(spec) > 4 else True
        eb = data.edit_bones.new(bn)
        eb.head = Vector(head)
        eb.tail = Vector(tail)
        d = (eb.tail - eb.head).normalized()
        if abs(d.y) > 0.75:
            eb.align_roll(Vector((0, 0, 1)))
        else:
            eb.align_roll(Vector((0, -1, 0)))
        eb.use_deform = deform
        if parent:
            eb.parent = data.edit_bones[parent]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm


def auto_skin(meshes, arm, exclude=()):
    """Bone-heat weights, ignoring `exclude` bones (facial rig, IK helpers)."""
    saved = {}
    for b in arm.data.bones:
        saved[b.name] = b.use_deform
        if b.name in exclude:
            b.use_deform = False
    for me in meshes:
        C.deselect_all()
        me.select_set(True)
        arm.select_set(True)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
        empty_groups = [vg for vg in me.vertex_groups if vg.name in exclude]
        for vg in empty_groups:
            me.vertex_groups.remove(vg)
    for b in arm.data.bones:
        b.use_deform = saved[b.name]


def rigid_skin(mesh, arm, bone):
    C.apply_transform(mesh)
    mesh.vertex_groups.clear()
    vg = mesh.vertex_groups.new(name=bone)
    vg.add(list(range(len(mesh.data.vertices))), 1.0, "REPLACE")
    mesh.parent = arm
    mod = mesh.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def limit_influences(mesh, max_inf=4, min_w=0.02):
    """glTF allows 4 joints per vertex in one set; prune and renormalise."""
    me = mesh.data
    groups = {vg.index: vg for vg in mesh.vertex_groups}
    for v in me.vertices:
        ws = sorted([(g.weight, g.group) for g in v.groups], reverse=True)
        keep = [(w, g) for w, g in ws[:max_inf] if w >= min_w] or ws[:1]
        drop = [g for w, g in ws if (w, g) not in keep]
        for g in drop:
            groups[g].remove([v.index])
        tot = sum(w for w, g in keep)
        for w, g in keep:
            groups[g].add([v.index], w / tot, "REPLACE")


# ---------------------------------------------------------------------------
# IK helpers
# ---------------------------------------------------------------------------

def add_ik(arm, bone, target_name, pole_name=None, chain=2, pole_angle=0.0):
    tgt = C.empty(target_name, (0, 0, 0), size=0.03)
    pb = arm.pose.bones[bone]
    con = pb.constraints.new("IK")
    con.name = "IK_" + target_name
    con.target = tgt
    con.chain_count = chain
    con.use_tail = True
    pole = None
    if pole_name:
        pole = C.empty(pole_name, (0, 0, 0), size=0.03)
        con.pole_target = pole
        con.pole_angle = math.radians(pole_angle)
    con.influence = 0.0
    return tgt, pole, con


# ---------------------------------------------------------------------------
# Baking
# ---------------------------------------------------------------------------

class Baker:
    """Bakes anim.Clip objects into Blender actions on NLA tracks."""

    def __init__(self, arm, ik=None):
        self.arm = arm
        self.ik = ik or {}  # name -> (target_obj, pole_obj, constraint)
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.order = self._hierarchy_order()

    def _hierarchy_order(self):
        out = []

        def walk(b):
            out.append(b.name)
            for c in b.children:
                walk(c)
        for b in self.arm.data.bones:
            if b.parent is None:
                walk(b)
        return out

    def _to_local(self, bone, v):
        """armature-axes rot/loc/scale -> pose bone basis (loc, quat, scale)."""
        R3 = self.rest[bone].to_3x3()
        Rinv = R3.inverted()
        q = Quaternion()
        if "r" in v:
            rx, ry, rz = (math.radians(a) for a in v["r"])
            Rw = (Matrix.Rotation(rz, 3, "Z") @ Matrix.Rotation(ry, 3, "Y") @ Matrix.Rotation(rx, 3, "X"))
            q = (Rinv @ Rw @ R3).to_quaternion()
        loc = Vector((0, 0, 0))
        if "l" in v:
            loc = Rinv @ Vector(v["l"])
        sc = Vector((1, 1, 1))
        if "s" in v:
            # scale authored in armature axes; approximate by the bone's axes
            s = Vector(v["s"])
            M = Rinv @ Matrix.Diagonal(s) @ R3
            sc = Vector((abs(M[0][0]), abs(M[1][1]), abs(M[2][2])))
        return loc, q, sc

    def _apply_fk(self, pose):
        for pb in self.arm.pose.bones:
            v = pose.get(pb.name)
            if v:
                loc, q, sc = self._to_local(pb.name, v)
            else:
                loc, q, sc = Vector((0, 0, 0)), Quaternion(), Vector((1, 1, 1))
            pb.location = loc
            pb.rotation_quaternion = q
            pb.scale = sc

    def bake(self, clip):
        arm = self.arm
        scn = bpy.context.scene
        n = clip.frames
        visual = []
        for f in range(n):
            t = f / A.FPS
            pose = clip.pose_at(t)
            self._apply_fk(pose)
            iks = clip.ik_at(t)
            for name, (tgt, pole, con) in self.ik.items():
                if name in iks:
                    pos, w = iks[name]
                    if pos is not None:
                        tgt.location = Vector(pos)
                    con.influence = w
                    if pole is not None and name in clip.poles:
                        pole.location = Vector(clip.poles[name])
                else:
                    con.influence = 0.0
            bpy.context.view_layer.update()
            visual.append({pb.name: pb.matrix.copy() for pb in arm.pose.bones})
        for name, (tgt, pole, con) in self.ik.items():
            con.influence = 0.0
        # convert visual (pose space) -> basis per bone
        if arm.animation_data is None:
            arm.animation_data_create()
        act = bpy.data.actions.new(clip.name)
        act.use_fake_user = True
        arm.animation_data.action = act
        frames = list(range(n)) + ([n] if clip.loop else [])
        prev_q = {}
        for f in frames:
            vis = visual[f % n]
            for bn in self.order:
                b = arm.data.bones[bn]
                pb = arm.pose.bones[bn]
                if b.parent:
                    M = (self.rest[bn].inverted() @ self.rest[b.parent.name]) @ vis[b.parent.name].inverted() @ vis[bn]
                else:
                    M = self.rest[bn].inverted() @ vis[bn]
                loc, q, sc = M.decompose()
                if bn in prev_q and prev_q[bn].dot(q) < 0:
                    q.negate()
                prev_q[bn] = q.copy()
                pb.location = loc
                pb.rotation_quaternion = q
                pb.scale = sc
                pb.keyframe_insert("location", frame=f)
                pb.keyframe_insert("rotation_quaternion", frame=f)
                pb.keyframe_insert("scale", frame=f)
        for fc in _fcurves(act):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        track = arm.animation_data.nla_tracks.new()
        track.name = clip.name
        track.strips.new(clip.name, 0, act)
        track.mute = True
        arm.animation_data.action = None
        self._apply_fk({})
        return act


def _fcurves(act):
    if hasattr(act, "layers") and len(act.layers) > 0:
        out = []
        for layer in act.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    out.extend(bag.fcurves)
        if out:
            return out
    return list(getattr(act, "fcurves", []))


def pose_frame(arm, clip, t, ik=None):
    """Apply one frame of a clip (for review renders)."""
    b = Baker(arm, ik)
    pose = clip.pose_at(t)
    b._apply_fk(pose)
    iks = clip.ik_at(t)
    for name, (tgt, pole, con) in (ik or {}).items():
        if name in iks:
            pos, w = iks[name]
            if pos is not None:
                tgt.location = Vector(pos)
            con.influence = w
            if pole is not None and name in clip.poles:
                pole.location = Vector(clip.poles[name])
        else:
            con.influence = 0.0
    bpy.context.view_layer.update()
