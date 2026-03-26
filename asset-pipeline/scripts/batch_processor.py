"""
Batch JSON'u okuyup her asset icin pipeline calistiran orkestrator.

asset-queue-batch1.json formatini pipeline_runner'a baglar.
Material tanimlarini ambientCG query'lere veya procedural preset'lere cevirir.

Kullanim (standalone — Blender disinda, texture indirme icin):
    python3 batch_processor.py --json ../asset-queue-batch1.json --list
    python3 batch_processor.py --json ../asset-queue-batch1.json --download-textures

Kullanim (MCP ile — Claude batch uretimi yapar):
    Bu script dogrudan calistirilmaz, Claude MCP uzerinden asset'leri
    tek tek isler. batch_processor sadece JSON'u parse eder ve
    her asset icin gerekli parametreleri cikarir.
"""

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Material path -> ambientCG query eslestirmesi
MATERIAL_QUERY_MAP = {
    "woods/oak_rough": "wood oak",
    "woods/oak_polished": "wood polished",
    "woods/oak_dark": "wood dark",
    "woods/oak_cut": "wood cut",
    "woods/pine_clean": "wood planks",
    "woods/pine_weathered": "wood weathered",
    "woods/birch_rough": "wood birch",
    "woods/birch_charred": "wood dark burnt",
    "woods/bark_oak": "bark tree",
    "woods/cork": "cork",
    "metals/iron_dark": "metal dark",
    "metals/iron_rusty": "rusty metal",
    "metals/bronze_aged": "bronze aged",
    "metals/gold_polished": "gold metal",
    "metals/silver_polished": "silver metal",
    "stones/castle_wall": "stone wall",
    "stones/floor_cobble": "cobblestone",
    "stones/rock_mossy": "rock mossy",
    "stones/river_smooth": "rock smooth",
    "fabrics/burlap": "burlap fabric",
    "fabrics/cloth_torn": "cloth fabric",
    "fabrics/rope_hemp": "rope",
    "leather/leather_brown": "leather brown",
    "leather/leather_rough": "leather rough",
    "organic/hay_dry": "hay straw",
    "organic/wicker": "wicker",
    "foliage/leaves_green": "leaves green",
    "foliage/grass_alpha": "grass",
    "paper/label_worn": "paper old",
}

# Procedural preset eslestirmesi (JSON'daki "type": "procedural" icin)
PROCEDURAL_PRESET_MAP = {
    "glass_dark_green": "glass_dark_green",
    "glass_clear": "glass_clear",
    "glass_brown": "glass_brown",
    "bronze_aged": "bronze_aged",
    "iron_dark": "iron_dark",
    "iron_rusty": "iron_rusty",
    "gold_polished": "gold_polished",
    "silver_polished": "silver_polished",
    "wax_white": None,  # solid color fallback
    "wax_beeswax": None,
    "flame_orange": None,
}


def load_batch(json_path):
    """Batch JSON'u yukle."""
    with open(json_path) as f:
        return json.load(f)


def parse_asset(asset_def):
    """Tek bir asset tanimini pipeline parametrelerine cevir.

    Returns:
        dict: {
            "id": "F016",
            "name": "barrel",
            "display_name": "Varil",
            "category": "furniture",
            "tri_budget": 1000,
            "texture_res": 1024,
            "materials": [...],  # parse edilmis materyal listesi
            "variants": ["clean", "old", "broken"],
            "export_formats": ["fbx", "glb"],
            "ai_prompt": "medieval wooden barrel...",
            "parsed_materials": [...]  # pipeline icin hazir
        }
    """
    result = {
        "id": asset_def["id"],
        "name": asset_def["name"],
        "display_name": asset_def.get("display_name", asset_def["name"]),
        "category": asset_def.get("category", "prop"),
        "tri_budget": asset_def.get("tri_budget", 5000),
        "texture_res": asset_def.get("texture_res", 1024),
        "variants": asset_def.get("variants", []),
        "export_formats": asset_def.get("export", ["fbx", "glb"]),
        "parsed_materials": [],
        "ai_prompt": generate_ai_prompt(asset_def),
    }

    # Materyalleri parse et
    for mat in asset_def.get("materials", []):
        parsed = parse_material(mat)
        result["parsed_materials"].append(parsed)

    return result


def parse_material(mat_def):
    """Tek bir materyal tanimini parse et.

    Input ornekleri:
        {"part": "body", "type": "library", "path": "woods/oak_rough"}
        {"part": "glass", "type": "procedural", "preset": "glass_dark_green"}
        {"part": "wick", "type": "color", "hex": "#1a1a1a"}
    """
    result = {
        "part": mat_def.get("part", "default"),
        "type": mat_def.get("type", "library"),
    }

    if result["type"] == "library":
        path = mat_def.get("path", "")
        result["texture_path"] = path
        result["ambientcg_query"] = MATERIAL_QUERY_MAP.get(path, path.replace("/", " "))

    elif result["type"] == "procedural":
        preset = mat_def.get("preset", "")
        result["preset"] = PROCEDURAL_PRESET_MAP.get(preset, preset)

    elif result["type"] == "color":
        result["hex"] = mat_def.get("hex", "#808080")
        result["roughness"] = mat_def.get("roughness", 0.5)
        result["metallic"] = mat_def.get("metallic", 0.0)

    return result


def generate_ai_prompt(asset_def):
    """Asset tanimindan Hunyuan3D/text-to-3D prompt'u uret."""
    name = asset_def.get("display_name", asset_def["name"])
    category = asset_def.get("category", "prop")
    tri_budget = asset_def.get("tri_budget", 5000)

    # Kategori bazli stil ipuclari
    style_hints = {
        "furniture": "medieval fantasy furniture",
        "prop": "medieval fantasy prop item",
        "weapon": "medieval fantasy weapon",
        "armor": "medieval fantasy armor piece",
        "nature": "natural outdoor element",
        "environment": "medieval building element",
        "consumable": "medieval food item",
    }
    style = style_hints.get(category, "medieval fantasy game asset")

    prompt = (
        f"A {name}, {style}, low poly game asset, "
        f"approximately {tri_budget} triangles, "
        f"clean topology, single object, centered at origin, "
        f"no background, studio lighting"
    )
    return prompt


def list_assets(json_path):
    """Batch'deki tum asset'leri listele."""
    batch = load_batch(json_path)
    print(f"Batch: {batch['batch']}")
    print(f"Toplam: {len(batch['assets'])} asset\n")

    for i, asset in enumerate(batch["assets"], 1):
        parsed = parse_asset(asset)
        mat_types = [m["type"] for m in parsed["parsed_materials"]]
        print(
            f"  [{i:2d}] {parsed['id']:6s} {parsed['name']:20s} "
            f"cat={parsed['category']:12s} tri={parsed['tri_budget']:5d} "
            f"mats={mat_types}"
        )


if __name__ == "__main__":
    json_path = None
    action = "list"

    for i, arg in enumerate(sys.argv):
        if arg == "--json" and i + 1 < len(sys.argv):
            json_path = sys.argv[i + 1]
        if arg == "--list":
            action = "list"
        if arg == "--download-textures":
            action = "download"

    if not json_path:
        # Default path
        json_path = os.path.join(
            os.path.dirname(os.path.dirname(SCRIPT_DIR)),
            "asset-queue-batch1.json"
        )

    if not os.path.exists(json_path):
        print(f"Hata: {json_path} bulunamadi")
        sys.exit(1)

    if action == "list":
        list_assets(json_path)
    elif action == "download":
        # Texture indirme
        from texture_bulk_download import download_all
        download_all()
