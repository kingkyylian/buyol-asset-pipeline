"""
Texture kutuphanesinden otomatik materyal atar:
- Asset metadata'sindan materyal bilgisi alir
- PBR texture setlerini baglar (diffuse, roughness, normal, metallic, AO, displacement)
- AO multiply entegrasyonu (Color x AO -> Base Color)
- Displacement -> Bump chain
- UV'ye gore texture mapping yapar
- ambientCG API ile otomatik texture indirir
- Procedural preset'ler: wood, metal, glass, stone, fabric + yeni preset'ler
- Solid color materyal destegi (hex)
"""

import bpy
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

UTILS_DIR = os.path.join(SCRIPT_DIR, "utils")
if UTILS_DIR not in sys.path:
    sys.path.insert(0, UTILS_DIR)

from blender_compat import get_principled_bsdf, get_material_output

TEXTURE_LIBRARY = os.path.join(
    os.path.dirname(SCRIPT_DIR), "textures", "library"
)


# === PBR MATERIAL FROM TEXTURE FILES ===

def create_pbr_material(name, texture_folder):
    """PBR materyal olusturur ve texture'lari baglar.
    AO multiply ve Displacement->Bump chain dahil."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = get_principled_bsdf(nodes)

    # Texture Coordinate + Mapping node'lari (tum texture'lar icin ortak)
    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    # --- Diffuse/Color ---
    diffuse_path = find_texture(texture_folder, "diffuse")
    diffuse_output = None
    if diffuse_path:
        tex_diffuse = nodes.new('ShaderNodeTexImage')
        tex_diffuse.image = bpy.data.images.load(diffuse_path)
        tex_diffuse.label = "Diffuse"
        links.new(mapping.outputs['Vector'], tex_diffuse.inputs['Vector'])
        diffuse_output = tex_diffuse.outputs['Color']

    # --- AO (Ambient Occlusion) ---
    ao_path = find_texture(texture_folder, "ao")
    if ao_path and diffuse_output:
        tex_ao = nodes.new('ShaderNodeTexImage')
        tex_ao.image = bpy.data.images.load(ao_path)
        tex_ao.image.colorspace_settings.name = 'Non-Color'
        tex_ao.label = "AO"
        links.new(mapping.outputs['Vector'], tex_ao.inputs['Vector'])

        # Color x AO (Multiply)
        ao_mix = nodes.new('ShaderNodeMix')
        ao_mix.data_type = 'RGBA'
        ao_mix.blend_type = 'MULTIPLY'
        ao_mix.inputs['Factor'].default_value = 1.0
        links.new(diffuse_output, ao_mix.inputs[6])  # A input (RGBA)
        links.new(tex_ao.outputs['Color'], ao_mix.inputs[7])  # B input (RGBA)
        links.new(ao_mix.outputs[2], bsdf.inputs['Base Color'])  # Result (RGBA)
    elif diffuse_output:
        links.new(diffuse_output, bsdf.inputs['Base Color'])

    # --- Roughness ---
    rough_path = find_texture(texture_folder, "roughness")
    if rough_path:
        tex_rough = nodes.new('ShaderNodeTexImage')
        tex_rough.image = bpy.data.images.load(rough_path)
        tex_rough.image.colorspace_settings.name = 'Non-Color'
        tex_rough.label = "Roughness"
        links.new(mapping.outputs['Vector'], tex_rough.inputs['Vector'])
        links.new(tex_rough.outputs['Color'], bsdf.inputs['Roughness'])

    # --- Metallic ---
    metal_path = find_texture(texture_folder, "metallic")
    if metal_path:
        tex_metal = nodes.new('ShaderNodeTexImage')
        tex_metal.image = bpy.data.images.load(metal_path)
        tex_metal.image.colorspace_settings.name = 'Non-Color'
        tex_metal.label = "Metallic"
        links.new(mapping.outputs['Vector'], tex_metal.inputs['Vector'])
        links.new(tex_metal.outputs['Color'], bsdf.inputs['Metallic'])

    # --- Normal + Displacement -> Bump chain ---
    normal_path = find_texture(texture_folder, "normal")
    disp_path = find_texture(texture_folder, "displacement")

    bump_output = None

    # Displacement -> Bump node
    if disp_path:
        tex_disp = nodes.new('ShaderNodeTexImage')
        tex_disp.image = bpy.data.images.load(disp_path)
        tex_disp.image.colorspace_settings.name = 'Non-Color'
        tex_disp.label = "Displacement"
        links.new(mapping.outputs['Vector'], tex_disp.inputs['Vector'])

        bump_node = nodes.new('ShaderNodeBump')
        bump_node.inputs['Strength'].default_value = 0.3
        bump_node.inputs['Distance'].default_value = 0.02
        links.new(tex_disp.outputs['Color'], bump_node.inputs['Height'])
        bump_output = bump_node.outputs['Normal']

    # Normal map
    if normal_path:
        tex_normal = nodes.new('ShaderNodeTexImage')
        tex_normal.image = bpy.data.images.load(normal_path)
        tex_normal.image.colorspace_settings.name = 'Non-Color'
        tex_normal.label = "Normal"
        links.new(mapping.outputs['Vector'], tex_normal.inputs['Vector'])

        normal_node = nodes.new('ShaderNodeNormalMap')
        links.new(tex_normal.outputs['Color'], normal_node.inputs['Color'])

        if bump_output:
            # Bump chain: Normal -> Bump node'un Normal input'una
            bump_node.inputs['Strength'].default_value = 0.2
            links.new(normal_node.outputs['Normal'], bump_node.inputs['Normal'])
            links.new(bump_output, bsdf.inputs['Normal'])
        else:
            links.new(normal_node.outputs['Normal'], bsdf.inputs['Normal'])
    elif bump_output:
        links.new(bump_output, bsdf.inputs['Normal'])

    return mat


def find_texture(folder, map_type):
    """Klasorde texture dosyasini arar"""
    extensions = ['.png', '.jpg', '.exr', '.tiff']
    keywords = {
        "diffuse": ["diffuse", "albedo", "basecolor", "base_color", "color"],
        "roughness": ["roughness", "rough"],
        "metallic": ["metallic", "metal", "metalness"],
        "normal": ["normalgl", "normal"],
        "ao": ["ao", "ambient_occlusion", "ambientocclusion", "occlusion"],
        "displacement": ["displacement", "height"],
    }

    if not os.path.exists(folder):
        return None

    for f in os.listdir(folder):
        f_lower = f.lower()
        # NormalDX'i atla, sadece NormalGL kullan
        if "normaldx" in f_lower:
            continue
        for keyword in keywords.get(map_type, []):
            if keyword in f_lower:
                for ext in extensions:
                    if f_lower.endswith(ext):
                        return os.path.join(folder, f)
    return None


def auto_assign_materials(obj_name, material_map):
    """
    material_map ornek:
    {
        "blade": {"texture_folder": "metals/steel_polished", "faces": "z > 0.1"},
        "handle": {"texture_folder": "woods/oak_rough", "faces": "z < -0.1"}
    }
    """
    obj = bpy.data.objects[obj_name]

    for part_name, config in material_map.items():
        mat = create_pbr_material(
            part_name,
            os.path.join(TEXTURE_LIBRARY, config["texture_folder"])
        )
        obj.data.materials.append(mat)


# === PROCEDURAL PRESETS ===

def create_procedural_wood(name="ProceduralWood", color=(0.35, 0.2, 0.1, 1.0),
                           roughness=0.7, scale=3.0, distortion=4.0):
    """Procedural ahsap materyali - bump dahil"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    # Texture Coordinate
    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    wave = nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'RINGS'
    wave.inputs['Scale'].default_value = scale
    wave.inputs['Distortion'].default_value = distortion
    wave.inputs['Detail'].default_value = 3.0
    links.new(mapping.outputs['Vector'], wave.inputs['Vector'])

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 8.0
    noise.inputs['Detail'].default_value = 6.0
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].color = (
        color[0] * 0.6, color[1] * 0.5, color[2] * 0.4, 1.0
    )

    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['Factor'].default_value = 0.3
    links.new(wave.outputs['Fac'], mix.inputs['A'])
    links.new(noise.outputs['Fac'], mix.inputs['B'])

    links.new(mix.outputs['Result'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = 0.0

    # Bump - ahsap damar kabartmasi
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.15
    bump.inputs['Distance'].default_value = 0.01
    links.new(wave.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def create_procedural_metal(name="ProceduralMetal", rust_amount=0.3,
                            base_color=(0.7, 0.7, 0.75, 1),
                            rust_color=(0.4, 0.2, 0.1, 1)):
    """Procedural metal materyali - bump dahil"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 15
    noise.inputs['Detail'].default_value = 8

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 1.0 - rust_amount
    ramp.color_ramp.elements[0].color = base_color
    ramp.color_ramp.elements[1].color = rust_color

    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])
    links.new(noise.outputs['Fac'], bsdf.inputs['Roughness'])

    invert = nodes.new('ShaderNodeInvert')
    links.new(noise.outputs['Fac'], invert.inputs['Color'])
    links.new(invert.outputs['Color'], bsdf.inputs['Metallic'])

    # Bump - metal yuzey kusuru
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.1
    noise2 = nodes.new('ShaderNodeTexNoise')
    noise2.inputs['Scale'].default_value = 40
    noise2.inputs['Detail'].default_value = 4
    links.new(noise2.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def create_procedural_glass(name="ProceduralGlass", color=(0.1, 0.3, 0.1, 1.0),
                            roughness=0.05, transparency=0.8):
    """Procedural cam materyali (sise, fener cami) - EEVEE uyumlu"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True

    # EEVEE seffaflik ayarlari
    try:
        mat.surface_render_method = 'DITHERED'
    except AttributeError:
        pass
    try:
        mat.blend_method = 'BLEND'
    except AttributeError:
        pass
    mat.use_backface_culling = False

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    bsdf.inputs['Base Color'].default_value = color
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['IOR'].default_value = 1.45

    # Transmission icin Blender 4+
    try:
        bsdf.inputs['Transmission Weight'].default_value = transparency
    except KeyError:
        try:
            bsdf.inputs['Transmission'].default_value = transparency
        except KeyError:
            pass

    # Alpha ayari
    try:
        bsdf.inputs['Alpha'].default_value = 1.0 - (transparency * 0.3)
    except KeyError:
        pass

    return mat


def create_procedural_stone(name="ProceduralStone", color=(0.4, 0.38, 0.35, 1.0),
                            roughness=0.85):
    """Procedural tas materyali (duvar, zemin) - guclu bump"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(tex_coord.outputs['Object'], mapping.inputs['Vector'])

    # Voronoi texture - tas deseni
    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.inputs['Scale'].default_value = 5.0
    voronoi.distance = 'EUCLIDEAN'
    links.new(mapping.outputs['Vector'], voronoi.inputs['Vector'])

    # Noise - yuzey detayi
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 12.0
    noise.inputs['Detail'].default_value = 8.0
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])

    # Color ramp
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].color = (
        color[0] * 0.7, color[1] * 0.65, color[2] * 0.6, 1.0
    )

    # Voronoi + noise karistir
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['Factor'].default_value = 0.4
    links.new(voronoi.outputs['Distance'], mix.inputs['A'])
    links.new(noise.outputs['Fac'], mix.inputs['B'])

    links.new(mix.outputs['Result'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    # Roughness varyasyon
    links.new(noise.outputs['Fac'], bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0

    # Bump - guclendirilmis
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.5
    bump.inputs['Distance'].default_value = 0.02
    links.new(voronoi.outputs['Distance'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_procedural_fabric(name="ProceduralFabric", color=(0.5, 0.4, 0.3, 1.0),
                             roughness=0.9):
    """Procedural kumas materyali (cuval, cadır, bez) - bump dahil"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    tex_coord = nodes.new('ShaderNodeTexCoord')
    mapping = nodes.new('ShaderNodeMapping')
    links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    # Wave texture - dokuma deseni
    wave1 = nodes.new('ShaderNodeTexWave')
    wave1.wave_type = 'BANDS'
    wave1.inputs['Scale'].default_value = 20.0
    wave1.inputs['Distortion'].default_value = 0.5
    links.new(mapping.outputs['Vector'], wave1.inputs['Vector'])

    wave2 = nodes.new('ShaderNodeTexWave')
    wave2.wave_type = 'BANDS'
    wave2.bands_direction = 'Y'
    wave2.inputs['Scale'].default_value = 20.0
    wave2.inputs['Distortion'].default_value = 0.5
    links.new(mapping.outputs['Vector'], wave2.inputs['Vector'])

    # Iki wave'i karistir - dokuma gorunumu
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['Factor'].default_value = 0.5
    links.new(wave1.outputs['Fac'], mix.inputs['A'])
    links.new(wave2.outputs['Fac'], mix.inputs['B'])

    # Color ramp
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].color = (
        color[0] * 0.85, color[1] * 0.85, color[2] * 0.85, 1.0
    )

    links.new(mix.outputs['Result'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = 0.0

    # Bump
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.2
    links.new(mix.outputs['Result'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def create_solid_color_material(name, hex_color, roughness=0.5, metallic=0.0):
    """Hex renk kodundan basit materyal olustur (mum fitili, basit renkler)."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = get_principled_bsdf(nodes)

    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    bsdf.inputs['Base Color'].default_value = (r, g, b, 1.0)
    bsdf.inputs['Roughness'].default_value = roughness
    bsdf.inputs['Metallic'].default_value = metallic
    return mat


# === YENI PROCEDURAL PRESET'LER ===

def create_procedural_wax(name="ProceduralWax", color=(0.95, 0.9, 0.75, 1.0)):
    """Mum balmumu materyali - hafif SSS gorunumu"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    # Hafif renk varyasyonu
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 5.0
    noise.inputs['Detail'].default_value = 3.0

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].color = (
        color[0] * 0.9, color[1] * 0.85, color[2] * 0.7, 1.0
    )
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.4
    bsdf.inputs['Metallic'].default_value = 0.0

    # SSS benzeri gorunum (Subsurface)
    try:
        bsdf.inputs['Subsurface Weight'].default_value = 0.3
        bsdf.inputs['Subsurface Radius'].default_value = (0.5, 0.3, 0.1)
    except KeyError:
        try:
            bsdf.inputs['Subsurface'].default_value = 0.3
        except KeyError:
            pass

    return mat


def create_procedural_bread(name="ProceduralBread"):
    """Ekmek kabuğu materyali - noise-driven crust"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    # Voronoi - kabuk crackle deseni
    voronoi = nodes.new('ShaderNodeTexVoronoi')
    voronoi.inputs['Scale'].default_value = 12.0

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 6.0
    noise.inputs['Detail'].default_value = 8.0

    # Mix textures
    mix = nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    mix.inputs['Factor'].default_value = 0.4
    links.new(voronoi.outputs['Distance'], mix.inputs['A'])
    links.new(noise.outputs['Fac'], mix.inputs['B'])

    # Color ramp - altin kahverengisi
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.65, 0.45, 0.2, 1.0)  # Acik kabuk
    ramp.color_ramp.elements[1].color = (0.35, 0.2, 0.08, 1.0)  # Koyu kabuk
    links.new(mix.outputs['Result'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.85
    bsdf.inputs['Metallic'].default_value = 0.0

    # Bump - kabuk kabartmasi
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.4
    links.new(voronoi.outputs['Distance'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def create_procedural_cheese(name="ProceduralCheese"):
    """Peynir materyali - sari rind + ic kisim"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 8.0
    noise.inputs['Detail'].default_value = 4.0

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.85, 0.7, 0.15, 1.0)  # Sari peynir
    ramp.color_ramp.elements[1].color = (0.75, 0.55, 0.1, 1.0)  # Koyu sari
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.6
    bsdf.inputs['Metallic'].default_value = 0.0

    # SSS - peynir icin
    try:
        bsdf.inputs['Subsurface Weight'].default_value = 0.2
    except KeyError:
        pass

    # Hafif bump
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.1
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def create_procedural_meat(name="ProceduralMeat"):
    """Pismis et materyali - dis koyu, ic pembe"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 4.0
    noise.inputs['Detail'].default_value = 6.0

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.45, 0.15, 0.08, 1.0)  # Pismis dis
    ramp.color_ramp.elements[1].color = (0.6, 0.25, 0.15, 1.0)   # Iceri dogru
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.7
    bsdf.inputs['Metallic'].default_value = 0.0

    # SSS
    try:
        bsdf.inputs['Subsurface Weight'].default_value = 0.15
    except KeyError:
        pass

    # Bump - et dokuma
    bump = nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.2
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])

    return mat


def create_procedural_ceramic(name="ProceduralCeramic", color=(0.9, 0.88, 0.82, 1.0)):
    """Seramik materyali - dusuk roughness, glazed gorunum"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = get_principled_bsdf(nodes)

    # Hafif renk varyasyonu
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 20.0
    noise.inputs['Detail'].default_value = 3.0

    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = color
    ramp.color_ramp.elements[1].color = (
        color[0] * 0.95, color[1] * 0.93, color[2] * 0.9, 1.0
    )
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    bsdf.inputs['Roughness'].default_value = 0.15  # Glazed - dusuk roughness
    bsdf.inputs['Metallic'].default_value = 0.0

    # Coat - glaze katmani
    try:
        bsdf.inputs['Coat Weight'].default_value = 0.4
        bsdf.inputs['Coat Roughness'].default_value = 0.05
    except KeyError:
        pass

    return mat


# === PROCEDURAL PRESET REGISTRY ===

PROCEDURAL_PRESETS = {
    # Wood presets - farkli scale/distortion ile cesitlilik
    "wood_oak": lambda name: create_procedural_wood(name, color=(0.35, 0.2, 0.1, 1.0), scale=3.0, distortion=4.0),
    "wood_pine": lambda name: create_procedural_wood(name, color=(0.45, 0.32, 0.18, 1.0), scale=4.0, distortion=3.0),
    "wood_birch": lambda name: create_procedural_wood(name, color=(0.6, 0.5, 0.35, 1.0), scale=2.5, distortion=5.0),
    "wood_dark": lambda name: create_procedural_wood(name, color=(0.15, 0.08, 0.04, 1.0), scale=3.5, distortion=3.5),
    "wood_charred": lambda name: create_procedural_wood(name, color=(0.05, 0.03, 0.02, 1.0), roughness=0.95, scale=2.0, distortion=6.0),
    # Metal presets - farkli renk/rust kombinasyonlari
    "iron_dark": lambda name: create_procedural_metal(name, rust_amount=0.1),
    "iron_rusty": lambda name: create_procedural_metal(name, rust_amount=0.6),
    "bronze_aged": lambda name: create_procedural_metal(name, rust_amount=0.4,
        base_color=(0.6, 0.45, 0.2, 1), rust_color=(0.3, 0.35, 0.2, 1)),
    "gold_polished": lambda name: create_procedural_metal(name, rust_amount=0.02,
        base_color=(0.95, 0.75, 0.2, 1), rust_color=(0.8, 0.6, 0.15, 1)),
    "silver_polished": lambda name: create_procedural_metal(name, rust_amount=0.05,
        base_color=(0.85, 0.85, 0.9, 1), rust_color=(0.5, 0.5, 0.5, 1)),
    # Glass presets
    "glass_clear": lambda name: create_procedural_glass(name, color=(0.9, 0.9, 0.9, 1.0), transparency=0.95),
    "glass_dark_green": lambda name: create_procedural_glass(name, color=(0.05, 0.2, 0.05, 1.0)),
    "glass_brown": lambda name: create_procedural_glass(name, color=(0.3, 0.15, 0.05, 1.0)),
    # Stone presets
    "stone_grey": lambda name: create_procedural_stone(name, color=(0.4, 0.38, 0.35, 1.0)),
    "stone_dark": lambda name: create_procedural_stone(name, color=(0.2, 0.18, 0.16, 1.0)),
    "stone_mossy": lambda name: create_procedural_stone(name, color=(0.3, 0.35, 0.25, 1.0)),
    # Fabric presets
    "burlap": lambda name: create_procedural_fabric(name, color=(0.5, 0.4, 0.3, 1.0)),
    "cloth_white": lambda name: create_procedural_fabric(name, color=(0.85, 0.82, 0.78, 1.0)),
    "cloth_torn": lambda name: create_procedural_fabric(name, color=(0.55, 0.45, 0.35, 1.0), roughness=0.95),
    "rope_hemp": lambda name: create_procedural_fabric(name, color=(0.45, 0.35, 0.2, 1.0), roughness=0.95),
    "leather_brown": lambda name: create_procedural_fabric(name, color=(0.3, 0.18, 0.08, 1.0), roughness=0.7),
    # Yeni preset'ler
    "wax_cream": lambda name: create_procedural_wax(name, color=(0.95, 0.9, 0.75, 1.0)),
    "wax_red": lambda name: create_procedural_wax(name, color=(0.7, 0.15, 0.1, 1.0)),
    "bread_crust": lambda name: create_procedural_bread(name),
    "cheese_yellow": lambda name: create_procedural_cheese(name),
    "meat_cooked": lambda name: create_procedural_meat(name),
    "ceramic_white": lambda name: create_procedural_ceramic(name),
    "ceramic_brown": lambda name: create_procedural_ceramic(name, color=(0.5, 0.35, 0.2, 1.0)),
    "bone_white": lambda name: create_solid_color_material(name, "#E8DCC8", roughness=0.6),
}


def create_material_from_preset(preset_name, mat_name=None):
    """Preset isminden materyal olustur."""
    if mat_name is None:
        mat_name = preset_name
    creator = PROCEDURAL_PRESETS.get(preset_name)
    if creator:
        return creator(mat_name)
    print(f"Warning: Unknown preset '{preset_name}'")
    return None


# === ambientCG ENTEGRASYONU ===

def fetch_ambientcg_texture(query, resolution="1K", fmt="JPG"):
    """ambientCG'den texture ara ve indir."""
    from ambientcg_downloader import search_and_download
    asset_id, maps = search_and_download(query, resolution=resolution, fmt=fmt)
    if asset_id:
        return os.path.join(TEXTURE_LIBRARY, asset_id)
    return None


def create_pbr_material_from_ambientcg(name, query, resolution="1K"):
    """ambientCG'den texture indirip PBR materyal olusturur."""
    texture_folder = fetch_ambientcg_texture(query, resolution=resolution)
    if texture_folder and os.path.exists(texture_folder):
        return create_pbr_material(name, texture_folder)
    print(f"Warning: Could not fetch texture for '{query}', falling back to procedural")
    return None
