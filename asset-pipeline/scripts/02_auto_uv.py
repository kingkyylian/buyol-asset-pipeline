"""
Modele otomatik UV unwrap uygular:
- Materyal sinirlarinda seam olusturur
- Aci bazli veya smart UV project uygular
- UV island'lari duzenler
- Overlap kontrolu yapar
"""

import bpy
import bmesh
import math


def auto_uv_unwrap(obj_name, method="angle_based", margin=0.02):
    obj = bpy.data.objects[obj_name]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')

    bm = bmesh.from_edit_mesh(obj.data)

    # Otomatik seam: keskin acilarda (60 derece ustu)
    auto_mark_seams_by_angle(bm, angle_threshold=60)

    # Materyal sinirlarinda seam
    auto_mark_seams_by_material(bm)

    bmesh.update_edit_mesh(obj.data)

    # Unwrap
    bpy.ops.mesh.select_all(action='SELECT')
    if method == "smart":
        bpy.ops.uv.smart_project(
            angle_limit=66,
            margin_method='SCALED',
            island_margin=margin
        )
    else:
        bpy.ops.uv.unwrap(method='ANGLE_BASED', margin=margin)

    # UV island'lari pack et (alan optimizasyonu)
    bpy.ops.uv.pack_islands(margin=margin)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Overlap kontrolu
    overlap = check_uv_overlap(obj)
    return {"method": method, "overlap_found": overlap}


def auto_mark_seams_by_angle(bm, angle_threshold=60):
    for edge in bm.edges:
        if len(edge.link_faces) == 2:
            angle = math.degrees(edge.calc_face_angle())
            if angle > angle_threshold:
                edge.seam = True


def auto_mark_seams_by_material(bm):
    for edge in bm.edges:
        face_mats = set()
        for face in edge.link_faces:
            face_mats.add(face.material_index)
        if len(face_mats) > 1:
            edge.seam = True


def check_uv_overlap(obj):
    """UV overlap kontrolu — bmesh ile island bounding box cakismasi kontrol eder."""
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)

    uv_layer = bm.loops.layers.uv.active
    if not uv_layer:
        bpy.ops.object.mode_set(mode='OBJECT')
        return False

    # Her face'in UV bounding box'ini topla
    face_bounds = []
    for face in bm.faces:
        us = [loop[uv_layer].uv.x for loop in face.loops]
        vs = [loop[uv_layer].uv.y for loop in face.loops]
        face_bounds.append((min(us), min(vs), max(us), max(vs)))

    # Basit O(n^2) overlap — kucuk mesh'ler icin yeterli
    overlap_count = 0
    n = len(face_bounds)
    for i in range(min(n, 500)):  # Performans limiti
        a = face_bounds[i]
        for j in range(i + 1, min(n, 500)):
            b = face_bounds[j]
            # AABB overlap testi
            if (a[0] < b[2] and a[2] > b[0] and
                a[1] < b[3] and a[3] > b[1]):
                overlap_count += 1

    bpy.ops.object.mode_set(mode='OBJECT')
    return overlap_count > 0
