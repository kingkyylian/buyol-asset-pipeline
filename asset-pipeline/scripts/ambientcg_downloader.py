"""
ambientCG API v3 texture downloader.
CC0 lisansli PBR texture setlerini arar ve indirir.

Kullanim (standalone):
    python3 ambientcg_downloader.py --query "rusty metal" --resolution 1K
    python3 ambientcg_downloader.py --query "wood oak" --resolution 2K --format PNG

Kullanim (import):
    from ambientcg_downloader import search_textures, download_texture_set
    results = search_textures("wood", limit=5)
    path = download_texture_set("Wood095", resolution="1K")
"""

import os
import sys
import json
import zipfile
import tempfile
import urllib.request
import urllib.parse

API_BASE = "https://ambientcg.com/api/v3"

# Default output: asset-pipeline/textures/library/
DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "textures", "library"
)

# Map tipleri ve Blender input isimleri
MAP_TYPES = {
    "Color": "Base Color",
    "Roughness": "Roughness",
    "Metalness": "Metallic",
    "NormalGL": "Normal",
    "Displacement": "Displacement",
    "AmbientOcclusion": "AO",
}


def search_textures(query, asset_type="Material", limit=10, sort="popular"):
    """ambientCG'de texture ara.

    Returns:
        list[dict]: Her biri {id, title, maps, downloads} iceren asset listesi
    """
    params = urllib.parse.urlencode({
        "q": query,
        "type": asset_type,
        "limit": limit,
        "sort": sort,
        "include": "downloads,maps,title",
    })
    url = f"{API_BASE}/assets?{params}"

    req = urllib.request.Request(url, headers={
        "User-Agent": "BlenderAssetPipeline/1.0"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())

    return data.get("assets", [])


def get_download_url(asset_id, resolution="1K", fmt="JPG"):
    """Belirli bir asset icin indirme URL'sini bul."""
    assets = search_textures(asset_id, limit=1)
    if not assets:
        return None

    target_attr = f"{resolution}-{fmt}"
    for dl in assets[0].get("downloads", []):
        if dl["attributes"] == target_attr:
            return dl["url"]

    # Fallback: istenen resolution yoksa en yakin olani bul
    for dl in assets[0].get("downloads", []):
        if dl["attributes"].startswith(resolution):
            return dl["url"]

    return None


def download_texture_set(asset_id, resolution="1K", fmt="JPG", output_dir=None):
    """PBR texture setini indir ve cikar.

    Args:
        asset_id: ambientCG asset ID (ornek: "Wood095")
        resolution: "1K", "2K", "4K", "8K" (default: "1K")
        fmt: "JPG" veya "PNG" (default: "JPG")
        output_dir: Cikti klasoru (default: textures/library/{asset_id}/)

    Returns:
        dict: {map_type: dosya_yolu} seklinde indirilen map'ler
    """
    if output_dir is None:
        output_dir = os.path.join(DEFAULT_OUTPUT, asset_id)

    os.makedirs(output_dir, exist_ok=True)

    # Indirme URL'sini bul
    zip_url = f"https://ambientcg.com/get?file={asset_id}_{resolution}-{fmt}.zip"

    # Zip'i indir
    print(f"Downloading {asset_id} ({resolution}-{fmt})...")
    tmp_zip = os.path.join(tempfile.gettempdir(), f"{asset_id}_{resolution}-{fmt}.zip")

    req = urllib.request.Request(zip_url, headers={
        "User-Agent": "BlenderAssetPipeline/1.0"
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        with open(tmp_zip, 'wb') as f:
            f.write(resp.read())

    # Zip'i ac ve texture dosyalarini cikar
    downloaded_maps = {}
    with zipfile.ZipFile(tmp_zip, 'r') as zf:
        for name in zf.namelist():
            # Sadece texture dosyalarini cikar (jpg/png)
            ext = os.path.splitext(name)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.exr'):
                continue

            # Map tipini belirle
            map_type = _identify_map_type(name)
            if map_type:
                out_path = os.path.join(output_dir, name)
                with zf.open(name) as src, open(out_path, 'wb') as dst:
                    dst.write(src.read())
                downloaded_maps[map_type] = out_path
                print(f"  Extracted: {name} -> {map_type}")

    # Temizle
    os.remove(tmp_zip)

    # Metadata kaydet
    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, 'w') as f:
        json.dump({
            "asset_id": asset_id,
            "resolution": resolution,
            "format": fmt,
            "license": "CC0",
            "source": "ambientcg.com",
            "maps": {k: os.path.basename(v) for k, v in downloaded_maps.items()}
        }, f, indent=2)

    print(f"Done! {len(downloaded_maps)} maps downloaded to {output_dir}")
    return downloaded_maps


def _identify_map_type(filename):
    """Dosya adindan map tipini belirle."""
    name_lower = filename.lower()
    # Oncelik sirasi onemli: NormalGL, NormalDX ayirt edilmeli
    if "normalgl" in name_lower:
        return "normal"
    if "normaldx" in name_lower:
        return "normal_dx"  # DirectX normal map (kullanmiyoruz)
    if "color" in name_lower or "albedo" in name_lower or "diffuse" in name_lower:
        return "diffuse"
    if "roughness" in name_lower:
        return "roughness"
    if "metalness" in name_lower or "metallic" in name_lower:
        return "metallic"
    if "displacement" in name_lower:
        return "displacement"
    if "ambientocclusion" in name_lower or "_ao" in name_lower:
        return "ao"
    # Preview image (buyuk kare gorsel)
    if filename.endswith(".png") and "_" not in os.path.basename(filename).split(".")[0][-3:]:
        return None  # Preview, skip
    return None


def search_and_download(query, resolution="1K", fmt="JPG", output_dir=None, limit=1):
    """Ara ve ilk sonucu indir. Convenience function.

    Returns:
        tuple: (asset_id, downloaded_maps_dict) veya (None, None)
    """
    results = search_textures(query, limit=limit)
    if not results:
        print(f"No results for '{query}'")
        return None, None

    asset = results[0]
    asset_id = asset["id"]
    print(f"Found: {asset.get('title', asset_id)} ({asset_id})")
    print(f"  Available maps: {asset.get('maps', [])}")

    maps = download_texture_set(asset_id, resolution=resolution, fmt=fmt,
                                output_dir=output_dir)
    return asset_id, maps


# === CLI ===
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ambientCG PBR Texture Downloader")
    sub = parser.add_subparsers(dest="command")

    # Search
    search_cmd = sub.add_parser("search", help="Texture ara")
    search_cmd.add_argument("query", help="Arama terimi")
    search_cmd.add_argument("--limit", type=int, default=10)
    search_cmd.add_argument("--sort", default="popular",
                           choices=["popular", "latest", "downloads"])

    # Download
    dl_cmd = sub.add_parser("download", help="Texture indir")
    dl_cmd.add_argument("asset_id", help="Asset ID (ornek: Wood095)")
    dl_cmd.add_argument("--resolution", "-r", default="1K",
                       choices=["1K", "2K", "4K", "8K"])
    dl_cmd.add_argument("--format", "-f", default="JPG", choices=["JPG", "PNG"])
    dl_cmd.add_argument("--output", "-o", help="Cikti klasoru")

    # Search + Download
    auto_cmd = sub.add_parser("auto", help="Ara ve ilk sonucu indir")
    auto_cmd.add_argument("query", help="Arama terimi")
    auto_cmd.add_argument("--resolution", "-r", default="1K",
                         choices=["1K", "2K", "4K", "8K"])
    auto_cmd.add_argument("--format", "-f", default="JPG", choices=["JPG", "PNG"])
    auto_cmd.add_argument("--output", "-o", help="Cikti klasoru")

    args = parser.parse_args()

    if args.command == "search":
        results = search_textures(args.query, limit=args.limit, sort=args.sort)
        for a in results:
            print(f"  {a['id']:30s}  {a.get('title', ''):30s}  maps: {a.get('maps', [])}")

    elif args.command == "download":
        download_texture_set(args.asset_id, resolution=args.resolution,
                           fmt=args.format, output_dir=args.output)

    elif args.command == "auto":
        search_and_download(args.query, resolution=args.resolution,
                          fmt=args.format, output_dir=args.output)

    else:
        parser.print_help()
