"""
Toplu export:
- FBX (Unity/Unreal) - texture embed dahil
- GLB (web/three.js)
- Thumbnail render (1024x1024 PNG) - adaptive kamera ile
"""

import bpy
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

EXPORT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports"
)


def batch_export(obj_name, output_dir=None, formats=None):
    if output_dir is None:
        output_dir = EXPORT_DIR
    if formats is None:
        formats = ["fbx", "glb"]

    obj = bpy.data.objects[obj_name]

    # Sadece asset'i sec
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    results = {}

    for fmt in formats:
        filepath = os.path.join(output_dir, fmt, f"{obj_name}.{fmt}")
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        if fmt == "fbx":
            bpy.ops.export_scene.fbx(
                filepath=filepath,
                use_selection=True,
                apply_scale_options='FBX_SCALE_ALL',
                mesh_smooth_type='FACE',
                use_mesh_modifiers=True,
                path_mode='COPY',
                embed_textures=True
            )
        elif fmt == "glb":
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                use_selection=True,
                export_format='GLB',
                export_apply=True
            )

        results[fmt] = filepath

    # Kamerayi objeye frame'le (thumbnail render oncesi)
    frame_camera_before_render(obj)

    # Thumbnail render
    thumb_path = os.path.join(output_dir, "thumbnails", f"{obj_name}.png")
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    render_thumbnail(thumb_path)
    results["thumbnail"] = thumb_path

    return results


def frame_camera_before_render(target_obj):
    """Render oncesi kamerayi objeye otomatik konumlandir."""
    try:
        from importlib import import_module
        # 01_scene_setup'dan frame_camera_to_object fonksiyonunu import et
        scene_setup_path = os.path.join(SCRIPT_DIR, "01_scene_setup.py")
        if os.path.exists(scene_setup_path):
            import importlib.util
            spec = importlib.util.spec_from_file_location("scene_setup", scene_setup_path)
            scene_setup = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(scene_setup)
            scene_setup.frame_camera_to_object(target_obj)
            return
    except Exception as e:
        print(f"Warning: Could not import frame_camera_to_object: {e}")

    # Fallback: manual framing
    _fallback_frame_camera(target_obj)


def _fallback_frame_camera(target_obj):
    """Fallback kamera framing - import basarisiz olursa."""
    import math
    from mathutils import Vector

    cam_obj = bpy.context.scene.camera
    if cam_obj is None:
        return

    bbox_corners = [target_obj.matrix_world @ Vector(c) for c in target_obj.bound_box]
    center = sum(bbox_corners, Vector()) / 8
    radius = max((v - center).length for v in bbox_corners)
    radius = max(radius, 0.1)

    fov = cam_obj.data.angle
    dist = (radius / math.tan(fov / 2)) * 1.5

    azimuth = math.radians(45)
    elevation = math.radians(55)

    cam_x = center.x + dist * math.cos(elevation) * math.sin(azimuth)
    cam_y = center.y - dist * math.cos(elevation) * math.cos(azimuth)
    cam_z = center.z + dist * math.sin(elevation)

    cam_obj.location = (cam_x, cam_y, cam_z)

    direction = center - cam_obj.location
    rot_quat = direction.to_track_quat('-Z', 'Y')
    cam_obj.rotation_euler = rot_quat.to_euler()


def render_thumbnail(output_path):
    scene = bpy.context.scene
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.film_transparent = True
    bpy.ops.render.render(write_still=True)
