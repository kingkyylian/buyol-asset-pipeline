"""
Batch 1 icin gereken texture'lari ambientCG'den toplu indirir.
Indirilen texture'lar batch JSON'daki path yapisina eslestirilir.

Kullanim:
    python3 texture_bulk_download.py
    python3 texture_bulk_download.py --dry-run   # Sadece listele, indirme
"""

import os
import sys
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ambientcg_downloader import search_and_download, search_textures

TEXTURE_LIBRARY = os.path.join(
    os.path.dirname(SCRIPT_DIR), "textures", "library"
)

# Batch 1 JSON'daki material path'leri -> ambientCG arama sorgusu
MATERIAL_TO_QUERY = {
    # Woods
    "woods/oak_rough": "wood oak",
    "woods/oak_polished": "wood polished",
    "woods/oak_dark": "wood dark",
    "woods/oak_cut": "wood cut",
    "woods/pine_clean": "wood planks",
    "woods/pine_weathered": "wood weathered",
    "woods/birch_rough": "wood birch",
    "woods/birch_charred": "wood dark",
    "woods/bark_oak": "bark tree",
    "woods/cork": "cork",
    # Metals
    "metals/iron_dark": "metal dark",
    "metals/iron_rusty": "rusty metal",
    "metals/bronze_aged": "metal",
    "metals/gold_polished": "gold metal",
    "metals/silver_polished": "silver metal",
    # Stones
    "stones/castle_wall": "stone wall",
    "stones/floor_cobble": "cobblestone",
    "stones/rock_mossy": "rock mossy",
    "stones/river_smooth": "rock smooth",
    # Fabrics
    "fabrics/burlap": "fabric rough",
    "fabrics/cloth_torn": "cloth fabric",
    "fabrics/rope_hemp": "rope",
    # Leather
    "leather/leather_brown": "leather brown",
    "leather/leather_rough": "leather rough",
    # Organic
    "organic/hay_dry": "straw",
    "organic/wicker": "wicker",
    # Foliage
    "foliage/leaves_green": "leaf",
    "foliage/grass_alpha": "grass",
    # Paper
    "paper/label_worn": "paper",
}


def download_all(resolution="1K", fmt="JPG", dry_run=False):
    """Tum batch 1 texture'larini indir."""
    total = len(MATERIAL_TO_QUERY)
    downloaded = 0
    skipped = 0
    failed = 0

    for mat_path, query in MATERIAL_TO_QUERY.items():
        target_dir = os.path.join(TEXTURE_LIBRARY, mat_path)

        # Zaten indirilmis mi?
        if os.path.exists(target_dir) and any(
            f.endswith(('.jpg', '.png')) for f in os.listdir(target_dir)
        ):
            print(f"  [SKIP] {mat_path} — zaten mevcut")
            skipped += 1
            continue

        print(f"\n[{downloaded + skipped + failed + 1}/{total}] {mat_path} <- '{query}'")

        if dry_run:
            results = search_textures(query, limit=1)
            if results:
                print(f"  [DRY] Bulundu: {results[0]['id']} — {results[0].get('title', '')}")
            else:
                print(f"  [DRY] Sonuc yok!")
                failed += 1
            continue

        # Indir
        try:
            asset_id, maps = search_and_download(
                query, resolution=resolution, fmt=fmt
            )
            if asset_id and maps:
                # ambientCG klasorunden hedef klasore kopyala/tasi
                src_dir = os.path.join(TEXTURE_LIBRARY, asset_id)
                os.makedirs(target_dir, exist_ok=True)

                for map_type, src_path in maps.items():
                    if os.path.exists(src_path):
                        dst_path = os.path.join(target_dir, os.path.basename(src_path))
                        shutil.copy2(src_path, dst_path)

                # Metadata kopyala
                meta_src = os.path.join(src_dir, "metadata.json")
                if os.path.exists(meta_src):
                    shutil.copy2(meta_src, os.path.join(target_dir, "metadata.json"))

                downloaded += 1
                print(f"  [OK] {len(maps)} map indirildi -> {target_dir}")
            else:
                failed += 1
                print(f"  [FAIL] Indirilemedi")
        except Exception as e:
            failed += 1
            print(f"  [ERROR] {e}")

    print(f"\n{'='*50}")
    print(f"TOPLAM: {total}")
    print(f"  Indirildi: {downloaded}")
    print(f"  Atlandi (mevcut): {skipped}")
    print(f"  Basarisiz: {failed}")
    print(f"{'='*50}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    resolution = "1K"
    fmt = "JPG"

    for i, arg in enumerate(sys.argv):
        if arg in ("-r", "--resolution") and i + 1 < len(sys.argv):
            resolution = sys.argv[i + 1]
        if arg in ("-f", "--format") and i + 1 < len(sys.argv):
            fmt = sys.argv[i + 1]

    if dry_run:
        print("=== DRY RUN — indirme yapilmayacak ===\n")

    download_all(resolution=resolution, fmt=fmt, dry_run=dry_run)
