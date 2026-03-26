"""
Yeni asset icin sahne hazirlar:
- Sahneyi temizler
- Standart isik setup'i kurar (guclendirilmis 3-point)
- Adaptive kamera ayarlar (obje boyutuna gore)
- Shadow catcher ground plane
- EEVEE kalite ayarlari
- Asset metadata'sini olusturur
"""

import bpy
import json
import math
from datetime import datetime
from mathutils import Vector


def setup_scene(asset_name, category="prop"):
    # Sahneyi temizle
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Standart 3-point lighting (guclendirilmis)
    create_three_point_lighting()

    # Shadow catcher ground plane
    create_shadow_catcher()

    # Thumbnail kamerasi (sonra frame_camera_to_object ile ayarlanacak)
    create_thumbnail_camera()

    # Render ayarlari
    scene = bpy.context.scene
    try:
        scene.render.engine = 'BLENDER_EEVEE'
    except TypeError:
        scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.film_transparent = True

    # EEVEE kalite ayarlari
    setup_eevee_quality(scene)

    # Metadata
    metadata = {
        "asset_name": asset_name,
        "category": category,
        "created": datetime.now().isoformat(),
        "status": "wip",
        "poly_budget": get_poly_budget(category),
        "texture_res": get_texture_res(category)
    }

    scene["asset_metadata"] = json.dumps(metadata)
    return metadata


def create_three_point_lighting():
    """Guclendirilmis 3-point lighting - sicak/soguk tonlarla"""
    # Key Light - Sun, sag ust kose, sicak ton
    bpy.ops.object.light_add(type='SUN', location=(3, -3, 5))
    key = bpy.context.active_object
    key.name = "Key_Light"
    key.data.energy = 5.0
    key.data.color = (1.0, 0.95, 0.9)  # Sicak ton
    key.rotation_euler = (math.radians(45), 0, math.radians(45))

    # Fill Light - Area, sol taraf, soguk ton
    bpy.ops.object.light_add(type='AREA', location=(-3, 3, 3))
    fill = bpy.context.active_object
    fill.name = "Fill_Light"
    fill.data.energy = 2.5
    fill.data.size = 4.0
    fill.data.color = (0.9, 0.93, 1.0)  # Soguk ton
    fill.rotation_euler = (math.radians(45), 0, math.radians(-135))

    # Rim Light - Spot, arkadan
    bpy.ops.object.light_add(type='SPOT', location=(0, 4, 2))
    rim = bpy.context.active_object
    rim.name = "Rim_Light"
    rim.data.energy = 3.0
    rim.data.spot_size = math.radians(45)
    rim.data.color = (1.0, 1.0, 1.0)
    rim.rotation_euler = (math.radians(70), 0, math.radians(180))


def create_shadow_catcher():
    """Golge yakalayici zemin duzlemi"""
    bpy.ops.mesh.primitive_plane_add(size=10, location=(0, 0, 0))
    plane = bpy.context.active_object
    plane.name = "Shadow_Catcher"
    # EEVEE shadow catcher
    try:
        plane.is_shadow_catcher = True
    except AttributeError:
        # Eski Blender versiyonlarinda shadow catcher yok
        # Seffaf materyal ata
        mat = bpy.data.materials.new(name="ShadowCatcher")
        mat.use_nodes = True
        mat.shadow_method = 'NONE'
        plane.data.materials.append(mat)
        plane.hide_render = True


def setup_eevee_quality(scene):
    """EEVEE render kalite ayarlari"""
    eevee = scene.eevee
    try:
        eevee.use_shadows = True
        eevee.shadow_cube_size = '512'
    except AttributeError:
        pass
    try:
        eevee.use_ssr = True
        eevee.use_ssr_refraction = True
    except AttributeError:
        pass
    # Render samples
    try:
        scene.eevee.taa_render_samples = 64
    except AttributeError:
        pass


def create_thumbnail_camera():
    """Thumbnail render icin kamera olusturur (varsayilan pozisyon)"""
    bpy.ops.object.camera_add(location=(2.5, -2.5, 1.8))
    cam = bpy.context.active_object
    cam.name = "Thumbnail_Camera"
    cam.rotation_euler = (math.radians(65), 0, math.radians(45))
    cam.data.lens = 50
    bpy.context.scene.camera = cam


def frame_camera_to_object(target_obj, cam_obj=None, padding=1.5):
    """Kamerayi obje boyutuna gore otomatik konumlandirir.

    Objenin bounding box'unu hesaplar, kamerayi obje tamamen
    gorunecek sekilde uzaklastirip yonlendirir.

    Args:
        target_obj: Hedef obje
        cam_obj: Kamera objesi (None ise sahne kamerasini kullanir)
        padding: Ekstra bosluk carpani (1.5 = %50 bosluk)
    """
    if cam_obj is None:
        cam_obj = bpy.context.scene.camera
    if cam_obj is None:
        return

    # Objenin world-space bounding box'u
    bbox_corners = [target_obj.matrix_world @ Vector(c) for c in target_obj.bound_box]
    center = sum(bbox_corners, Vector()) / 8

    # Bounding sphere radius
    radius = max((v - center).length for v in bbox_corners)

    # Minimum radius (cok kucuk objeler icin)
    radius = max(radius, 0.1)

    # Kamera FOV'dan mesafe hesapla
    fov = cam_obj.data.angle  # radyan cinsinden
    dist = (radius / math.tan(fov / 2)) * padding

    # Gorus yonu: 45 derece azimut, ~55 derece elevation
    azimuth = math.radians(45)
    elevation = math.radians(55)

    # Kamera pozisyonu kuresel koordinatlardan
    cam_x = center.x + dist * math.cos(elevation) * math.sin(azimuth)
    cam_y = center.y - dist * math.cos(elevation) * math.cos(azimuth)
    cam_z = center.z + dist * math.sin(elevation)

    cam_obj.location = (cam_x, cam_y, cam_z)

    # Kamerayi merkeze yonlendir
    direction = center - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()


def get_poly_budget(category):
    budgets = {
        "prop": 5000,
        "weapon": 8000,
        "char": 15000,
        "env": 3000,
        "vehicle": 20000,
        "furniture": 5000,
    }
    return budgets.get(category, 5000)


def get_texture_res(category):
    res = {
        "prop": 1024,
        "weapon": 2048,
        "char": 2048,
        "env": 1024,
        "vehicle": 2048,
        "furniture": 1024,
    }
    return res.get(category, 1024)
