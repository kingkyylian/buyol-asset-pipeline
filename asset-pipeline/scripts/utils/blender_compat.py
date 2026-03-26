"""
Blender dil uyumluluk katmani.
Turkce, Ingilizce ve diger dillerde node isimlerinin farkli olmasi sorununu cozer.
Node'lari type ile bulur, isme bagli kalmaz.
"""


def find_node_by_type(nodes, node_type):
    """Node'u type ile bul (dil bagimsiz).

    Ornek type'lar:
        'BSDF_PRINCIPLED'  - Principled BSDF / Ilkeli BSDF
        'OUTPUT_MATERIAL'   - Material Output / Malzeme Ciktisi
        'TEX_IMAGE'         - Image Texture
        'NORMAL_MAP'        - Normal Map
        'MAPPING'           - Mapping
        'TEX_COORD'         - Texture Coordinate
        'MIX'               - Mix / Mix Color
        'VALTORGB'          - Color Ramp
        'TEX_NOISE'         - Noise Texture
        'TEX_WAVE'          - Wave Texture
        'BUMP'              - Bump
        'DISPLACEMENT'      - Displacement
        'INVERT'            - Invert
    """
    for n in nodes:
        if n.type == node_type:
            return n
    return None


def find_all_nodes_by_type(nodes, node_type):
    """Belirli type'daki tum node'lari bul."""
    return [n for n in nodes if n.type == node_type]


def get_principled_bsdf(nodes):
    """Principled BSDF node'unu bul (kisayol)."""
    return find_node_by_type(nodes, 'BSDF_PRINCIPLED')


def get_material_output(nodes):
    """Material Output node'unu bul (kisayol)."""
    return find_node_by_type(nodes, 'OUTPUT_MATERIAL')


def get_render_engine_name():
    """Blender versiyonuna gore dogru render engine ismini don."""
    import bpy
    version = bpy.app.version
    # Blender 4.0+ BLENDER_EEVEE_NEXT kullaniyor, 5.0+ tekrar BLENDER_EEVEE
    if version >= (5, 0, 0):
        return 'BLENDER_EEVEE'
    elif version >= (4, 0, 0):
        return 'BLENDER_EEVEE_NEXT'
    else:
        return 'BLENDER_EEVEE'
