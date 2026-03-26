# Blender Asset Üretim Pipeline'ı — Otomasyon İş Akışı
## 2 Haftalık Sprint Planı

---

## Genel Bakış

```
[Konsept/Referans] → [Modelleme] → [UV Unwrap] → [Texture] → [QA Check] → [Export]
      ↓                  ↓             ↓             ↓            ↓           ↓
  referans.json      model.blend    uv_check.py   texture.py   qa_report    .fbx/.glb
```

---

## HAFTA 1: Pipeline Kurulumu & Modelleme Otomasyonu

### Gün 1-2: Proje Yapısı & Standartlar

```
asset-pipeline/
├── config/
│   ├── pipeline_config.json       # Genel ayarlar (poly limit, texture res, export format)
│   ├── naming_convention.md       # İsimlendirme kuralları
│   └── quality_standards.md       # Kalite kriterleri
├── scripts/
│   ├── 01_scene_setup.py          # Sahne hazırlık scripti
│   ├── 02_auto_uv.py             # Otomatik UV unwrap
│   ├── 03_auto_texture.py        # Otomatik texture/materyal atama
│   ├── 04_qa_check.py            # Kalite kontrol (non-manifold, UV overlap vs.)
│   ├── 05_batch_export.py        # Toplu export (FBX, GLB, OBJ)
│   └── utils/
│       ├── mesh_utils.py          # Ortak mesh fonksiyonları
│       ├── material_utils.py      # Materyal yardımcıları
│       └── naming_utils.py        # İsimlendirme doğrulama
├── assets/
│   ├── _queue/                    # Sırada bekleyen asset konseptleri
│   ├── _wip/                      # Üzerinde çalışılan assetler
│   ├── _review/                   # QA bekleyen
│   └── _done/                     # Onaylı, export edilmiş
├── textures/
│   ├── library/                   # Tekrar kullanılabilir texture kütüphanesi
│   │   ├── metals/
│   │   ├── woods/
│   │   ├── fabrics/
│   │   └── stones/
│   └── generated/                 # Script ile üretilen texture'lar
├── exports/
│   ├── fbx/
│   ├── glb/
│   └── thumbnails/                # Otomatik render edilmiş önizlemeler
└── logs/
    └── pipeline.log               # İşlem logları
```

### İsimlendirme Kuralları

```
Format: {kategori}_{isim}_{varyant}_v{versiyon}
Örnekler:
  prop_sword_rusty_v01.blend
  weapon_axe_golden_v02.blend
  env_rock_large_v01.blend
  char_helmet_iron_v01.blend

Texture:
  T_{asset}_{map_type}.png
  T_sword_rusty_diffuse.png
  T_sword_rusty_roughness.png
  T_sword_rusty_normal.png
```

---

### Gün 3-4: Otomasyon Scriptleri

#### Script 1: Sahne Hazırlık (01_scene_setup.py)

```python
"""
Yeni asset için sahne hazırlar:
- Sahneyi temizler
- Standart ışık setup'ı kurar
- Kamera ayarlar (thumbnail render için)
- Asset metadata'sını oluşturur
"""

import bpy
import json
import os
from datetime import datetime

def setup_scene(asset_name, category="prop"):
    # Sahneyi temizle
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Standart 3-point lighting
    create_three_point_lighting()

    # Thumbnail kamerası
    create_thumbnail_camera()

    # Render ayarları
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_EEVEE_NEXT'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.film_transparent = True

    # Metadata
    metadata = {
        "asset_name": asset_name,
        "category": category,
        "created": datetime.now().isoformat(),
        "status": "wip",
        "poly_budget": get_poly_budget(category),
        "texture_res": get_texture_res(category)
    }

    # Custom property olarak kaydet
    scene["asset_metadata"] = json.dumps(metadata)

    return metadata

def get_poly_budget(category):
    budgets = {
        "prop": 5000,
        "weapon": 8000,
        "char": 15000,
        "env": 3000,
        "vehicle": 20000
    }
    return budgets.get(category, 5000)

def get_texture_res(category):
    res = {
        "prop": 1024,
        "weapon": 2048,
        "char": 2048,
        "env": 1024,
        "vehicle": 2048
    }
    return res.get(category, 1024)
```

#### Script 2: Otomatik UV (02_auto_uv.py)

```python
"""
Modele otomatik UV unwrap uygular:
- Materyal sınırlarında seam oluşturur
- Açı bazlı veya smart UV project uygular
- UV island'ları düzenler
- Overlap kontrolü yapar
"""

import bpy
import bmesh

def auto_uv_unwrap(obj_name, method="angle_based", margin=0.02):
    obj = bpy.data.objects[obj_name]
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')

    bm = bmesh.from_edit_mesh(obj.data)

    # Otomatik seam: keskin açılarda (60 derece üstü)
    auto_mark_seams_by_angle(bm, angle_threshold=60)

    # Materyal sınırlarında seam
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

    # UV island'ları pack et (alan optimizasyonu)
    bpy.ops.uv.pack_islands(margin=margin)

    bpy.ops.object.mode_set(mode='OBJECT')

    # Overlap kontrolü
    overlap = check_uv_overlap(obj)
    return {"method": method, "overlap_found": overlap}

def auto_mark_seams_by_angle(bm, angle_threshold=60):
    import math
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
    # Basit overlap kontrolü
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    # UV overlap seçimi
    bpy.ops.uv.select_overlap()
    bpy.ops.object.mode_set(mode='OBJECT')
    return False  # Detaylı kontrol için genişletilebilir
```

#### Script 3: Otomatik Texture (03_auto_texture.py)

```python
"""
Texture kütüphanesinden otomatik materyal atar:
- Asset metadata'sından materyal bilgisi alır
- PBR texture setlerini bağlar (diffuse, roughness, normal, metallic)
- UV'ye göre texture mapping yapar
"""

import bpy
import os

TEXTURE_LIBRARY = "/path/to/asset-pipeline/textures/library/"

def create_pbr_material(name, texture_folder):
    """PBR materyal oluşturur ve texture'ları bağlar"""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes["Principled BSDF"]

    texture_maps = {
        "diffuse": "Base Color",
        "roughness": "Roughness",
        "metallic": "Metallic",
        "normal": None,  # Normal map özel bağlantı gerektirir
    }

    for map_type, input_name in texture_maps.items():
        # Texture dosyasını bul
        tex_path = find_texture(texture_folder, map_type)
        if not tex_path:
            continue

        # Image texture node oluştur
        tex_node = nodes.new('ShaderNodeTexImage')
        tex_node.image = bpy.data.images.load(tex_path)
        tex_node.label = map_type.capitalize()

        if map_type == "normal":
            # Normal map node
            normal_node = nodes.new('ShaderNodeNormalMap')
            links.new(tex_node.outputs['Color'], normal_node.inputs['Color'])
            links.new(normal_node.outputs['Normal'], bsdf.inputs['Normal'])
            tex_node.image.colorspace_settings.name = 'Non-Color'
        elif map_type in ("roughness", "metallic"):
            links.new(tex_node.outputs['Color'], bsdf.inputs[input_name])
            tex_node.image.colorspace_settings.name = 'Non-Color'
        else:
            links.new(tex_node.outputs['Color'], bsdf.inputs[input_name])

    return mat

def find_texture(folder, map_type):
    """Klasörde texture dosyasını arar"""
    extensions = ['.png', '.jpg', '.exr', '.tiff']
    keywords = {
        "diffuse": ["diffuse", "albedo", "basecolor", "base_color", "color"],
        "roughness": ["roughness", "rough"],
        "metallic": ["metallic", "metal"],
        "normal": ["normal", "norm", "nrm"],
        "ao": ["ao", "ambient_occlusion", "occlusion"]
    }

    if not os.path.exists(folder):
        return None

    for f in os.listdir(folder):
        f_lower = f.lower()
        for keyword in keywords.get(map_type, []):
            if keyword in f_lower:
                for ext in extensions:
                    if f_lower.endswith(ext):
                        return os.path.join(folder, f)
    return None

def auto_assign_materials(obj_name, material_map):
    """
    material_map örnek:
    {
        "blade": {"texture_folder": "metals/steel_polished", "faces": "z > 0.1"},
        "handle": {"texture_folder": "woods/oak_rough", "faces": "z < -0.1"}
    }
    """
    obj = bpy.data.objects[obj_name]

    for part_name, config in material_map.items():
        mat = create_pbr_material(part_name,
              os.path.join(TEXTURE_LIBRARY, config["texture_folder"]))
        obj.data.materials.append(mat)
        # Face atama mantığı buraya...
```

#### Script 4: QA Check (04_qa_check.py)

```python
"""
Asset kalite kontrolü:
- Poly sayısı budget içinde mi?
- Non-manifold edge var mı?
- UV overlap var mı?
- Materyal atanmamış face var mı?
- İsimlendirme doğru mu?
- Scale apply edilmiş mi?
- Origin doğru konumda mı?
"""

import bpy
import bmesh
import json

def run_qa_check(obj_name):
    obj = bpy.data.objects[obj_name]
    report = {
        "asset": obj_name,
        "passed": True,
        "checks": {}
    }

    # 1. Poly count
    poly_count = len(obj.data.polygons)
    metadata = json.loads(bpy.context.scene.get("asset_metadata", "{}"))
    budget = metadata.get("poly_budget", 10000)
    report["checks"]["poly_count"] = {
        "value": poly_count,
        "budget": budget,
        "pass": poly_count <= budget
    }

    # 2. Non-manifold edges
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode='EDIT')
    bm = bmesh.from_edit_mesh(obj.data)
    non_manifold = [e for e in bm.edges if not e.is_manifold]
    report["checks"]["non_manifold"] = {
        "count": len(non_manifold),
        "pass": len(non_manifold) == 0
    }
    bpy.ops.object.mode_set(mode='OBJECT')

    # 3. Scale applied
    scale_ok = all(abs(s - 1.0) < 0.001 for s in obj.scale)
    report["checks"]["scale_applied"] = {"pass": scale_ok}

    # 4. Rotation applied
    rot_ok = all(abs(r) < 0.001 for r in obj.rotation_euler)
    report["checks"]["rotation_applied"] = {"pass": rot_ok}

    # 5. Materials assigned
    has_mats = len(obj.data.materials) > 0
    report["checks"]["has_materials"] = {"pass": has_mats}

    # 6. UV layers
    has_uv = len(obj.data.uv_layers) > 0
    report["checks"]["has_uv"] = {"pass": has_uv}

    # 7. Origin at world center or base
    origin_ok = abs(obj.location.x) < 0.01 and abs(obj.location.y) < 0.01
    report["checks"]["origin_position"] = {"pass": origin_ok}

    # Overall
    report["passed"] = all(c["pass"] for c in report["checks"].values())

    return report

def print_qa_report(report):
    print(f"\n{'='*50}")
    print(f"QA REPORT: {report['asset']}")
    print(f"{'='*50}")
    for name, check in report["checks"].items():
        status = "✅ PASS" if check["pass"] else "❌ FAIL"
        detail = ""
        if "value" in check:
            detail = f" ({check['value']}/{check.get('budget', '?')})"
        if "count" in check:
            detail = f" ({check['count']} found)"
        print(f"  {status}  {name}{detail}")
    print(f"\n  OVERALL: {'✅ PASSED' if report['passed'] else '❌ FAILED'}")
    print(f"{'='*50}\n")
```

#### Script 5: Batch Export (05_batch_export.py)

```python
"""
Toplu export:
- FBX (Unity/Unreal)
- GLB (web/three.js)
- Thumbnail render (1024x1024 PNG)
"""

import bpy
import os

def batch_export(obj_name, output_dir, formats=["fbx", "glb"]):
    obj = bpy.data.objects[obj_name]

    # Sadece asset'i seç
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
                use_mesh_modifiers=True
            )
        elif fmt == "glb":
            bpy.ops.export_scene.gltf(
                filepath=filepath,
                use_selection=True,
                export_format='GLB',
                export_apply=True
            )

        results[fmt] = filepath

    # Thumbnail render
    thumb_path = os.path.join(output_dir, "thumbnails", f"{obj_name}.png")
    os.makedirs(os.path.dirname(thumb_path), exist_ok=True)
    render_thumbnail(thumb_path)
    results["thumbnail"] = thumb_path

    return results

def render_thumbnail(output_path):
    scene = bpy.context.scene
    scene.render.filepath = output_path
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.film_transparent = True
    bpy.ops.render.render(write_still=True)
```

---

### Gün 5: Pipeline Runner

```python
"""
pipeline_runner.py — Tek komutla tüm pipeline'ı çalıştırır

Kullanım:
  blender --background --python pipeline_runner.py -- --asset sword --category weapon
"""

import sys
import json
from datetime import datetime

# Script importları
from scripts.scene_setup import setup_scene
from scripts.auto_uv import auto_uv_unwrap
from scripts.auto_texture import auto_assign_materials
from scripts.qa_check import run_qa_check, print_qa_report
from scripts.batch_export import batch_export

def run_pipeline(asset_name, category, material_map=None):
    log = []

    # 1. Sahne hazırla
    log.append(f"[{timestamp()}] Setting up scene for {asset_name}")
    metadata = setup_scene(asset_name, category)

    # 2. Model zaten hazırsa (manuel veya AI ile üretilmiş)
    #    Bu adım manuel veya Blender MCP ile yapılır
    log.append(f"[{timestamp()}] Model expected in scene")

    # 3. UV Unwrap
    log.append(f"[{timestamp()}] Running auto UV unwrap")
    uv_result = auto_uv_unwrap(asset_name)
    log.append(f"[{timestamp()}] UV result: {uv_result}")

    # 4. Texture
    if material_map:
        log.append(f"[{timestamp()}] Assigning materials")
        auto_assign_materials(asset_name, material_map)

    # 5. QA Check
    log.append(f"[{timestamp()}] Running QA check")
    qa = run_qa_check(asset_name)
    print_qa_report(qa)

    if not qa["passed"]:
        log.append(f"[{timestamp()}] ❌ QA FAILED — asset not exported")
        return {"status": "failed", "qa": qa, "log": log}

    # 6. Export
    log.append(f"[{timestamp()}] Exporting")
    exports = batch_export(asset_name, "./exports/")

    # 7. Asset'i _done klasörüne taşı
    log.append(f"[{timestamp()}] ✅ Pipeline complete")

    return {"status": "success", "qa": qa, "exports": exports, "log": log}

def timestamp():
    return datetime.now().strftime("%H:%M:%S")
```

---

## HAFTA 2: Texture Otomasyonu & Batch Üretim

### Gün 6-7: Texture Üretim Otomasyonu

#### Seçenek A: Poly Haven Otomatik İndirme

```python
"""
Poly Haven API'sinden otomatik texture indirme
API: https://api.polyhaven.com
"""

import requests
import os

POLYHAVEN_API = "https://api.polyhaven.com/v1"

def search_textures(query, category="textures"):
    """Poly Haven'da texture ara"""
    url = f"{POLYHAVEN_API}/assets?type={category}&search={query}"
    response = requests.get(url)
    return response.json()

def download_texture_set(asset_id, resolution="1k", output_dir="./textures/library/"):
    """Tam PBR set indir (diffuse, roughness, normal, etc.)"""
    url = f"{POLYHAVEN_API}/files/{asset_id}"
    response = requests.get(url)
    files = response.json()

    maps = ["Diffuse", "nor_gl", "Rough", "Metal", "AO"]
    downloaded = []

    for map_name in maps:
        if map_name in files.get("Textures", {}):
            tex_data = files["Textures"][map_name]
            if resolution in tex_data:
                file_url = tex_data[resolution]["png"]["url"]

                save_path = os.path.join(output_dir, asset_id, f"{map_name}.png")
                os.makedirs(os.path.dirname(save_path), exist_ok=True)

                r = requests.get(file_url)
                with open(save_path, 'wb') as f:
                    f.write(r.content)

                downloaded.append(save_path)

    return downloaded

# Kullanım:
# results = search_textures("rusty metal")
# download_texture_set("rusty_metal_02", resolution="2k")
```

#### Seçenek B: Procedural Texture Generation

```python
"""
Blender'ın node sisteminde procedural texture üretimi
Texture dosyasına ihtiyaç duymaz, tamamen node-based
"""

import bpy

def create_procedural_metal(name="ProceduralMetal", rust_amount=0.3):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    bsdf = nodes["Principled BSDF"]

    # Noise texture for variation
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 15
    noise.inputs['Detail'].default_value = 8

    # Color ramp for rust pattern
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].position = 1.0 - rust_amount
    ramp.color_ramp.elements[0].color = (0.7, 0.7, 0.75, 1)  # clean metal
    ramp.color_ramp.elements[1].color = (0.4, 0.2, 0.1, 1)   # rust

    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], bsdf.inputs['Base Color'])

    # Roughness variation
    links.new(noise.outputs['Fac'], bsdf.inputs['Roughness'])

    # Metallic (less where rusty)
    invert = nodes.new('ShaderNodeInvert')
    links.new(noise.outputs['Fac'], invert.inputs['Color'])
    links.new(invert.outputs['Color'], bsdf.inputs['Metallic'])

    return mat
```

### Gün 8-9: Batch Asset Üretim

```python
"""
batch_produce.py — Birden fazla asset'i sırayla üretir

Kullanım:
  blender --background --python batch_produce.py -- --config batch_config.json
"""

# batch_config.json örneği:
BATCH_CONFIG = {
    "assets": [
        {
            "name": "prop_sword_rusty",
            "category": "weapon",
            "model_source": "template",  # template | ai_generate | import
            "template": "sword_base.blend",
            "materials": {
                "blade": {"type": "procedural", "preset": "rusty_metal", "rust": 0.4},
                "handle": {"type": "library", "path": "woods/oak_rough"},
                "guard": {"type": "library", "path": "metals/gold_ornate"}
            },
            "export": ["fbx", "glb"]
        },
        {
            "name": "prop_shield_wooden",
            "category": "prop",
            "model_source": "import",
            "import_path": "./models/shield.obj",
            "materials": {
                "body": {"type": "library", "path": "woods/pine_clean"},
                "rim": {"type": "procedural", "preset": "dark_iron"}
            },
            "export": ["fbx", "glb"]
        }
    ]
}

def batch_produce(config_path):
    import json
    with open(config_path) as f:
        config = json.load(f)

    results = []
    for asset in config["assets"]:
        print(f"\n{'='*60}")
        print(f"PRODUCING: {asset['name']}")
        print(f"{'='*60}")

        result = run_pipeline(
            asset_name=asset["name"],
            category=asset["category"],
            material_map=asset.get("materials")
        )
        results.append(result)

    # Özet rapor
    passed = sum(1 for r in results if r["status"] == "success")
    print(f"\n\nBATCH COMPLETE: {passed}/{len(results)} assets exported successfully")

    return results
```

### Gün 10: Claude MCP Entegrasyonu (AI-Assisted Modelleme)

```
Akış:
1. JSON'da asset tanımı yaz (isim, tür, detay seviyesi)
2. Claude MCP üzerinden Blender'da modeli üret
3. Pipeline scriptleri otomatik UV + texture + QA + export yapar

Komut:
  "prop_chest_wooden üret, low-poly, 3000 tri budget, ahşap texture"

  → Claude MCP: Blender'da modeller
  → 02_auto_uv.py: UV unwrap
  → 03_auto_texture.py: Poly Haven'dan ahşap texture indir + ata
  → 04_qa_check.py: Kontrol
  → 05_batch_export.py: FBX + GLB + thumbnail
```

---

## Gün 11-12: Watchdog & Otomasyon

```python
"""
file_watcher.py — Klasör izleyici
_queue klasörüne .json atıldığında pipeline otomatik başlar
"""

import time
import os
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class AssetQueueHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith('.json'):
            print(f"New asset queued: {event.src_path}")
            # Pipeline başlat
            config = json.load(open(event.src_path))
            os.system(f'blender --background --python pipeline_runner.py '
                      f'-- --config "{event.src_path}"')
            # Tamamlanınca _done'a taşı
            os.rename(event.src_path,
                      event.src_path.replace('_queue', '_done'))

if __name__ == "__main__":
    observer = Observer()
    observer.schedule(AssetQueueHandler(), "./assets/_queue/", recursive=False)
    observer.start()
    print("Watching _queue folder for new assets...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
```

---

## Gün 13-14: Test & Dökümantasyon

### Test Checklist
- [ ] Tek asset pipeline (baştan sona)
- [ ] Batch export (5+ asset)
- [ ] QA fail durumu (non-manifold, poly aşımı)
- [ ] Texture kütüphane sistemi
- [ ] Poly Haven entegrasyonu
- [ ] File watcher otomasyonu
- [ ] Export formatları (FBX → Unity import, GLB → three.js)

### Performans Hedefleri
- Tek asset pipeline: < 2 dakika (UV + texture + QA + export)
- Batch 10 asset: < 15 dakika
- Texture indirme (Poly Haven): < 30 saniye per set

---

## Özet: Tam Otomasyon Akışı

```
_queue/prop_sword.json  ←  Mehmet JSON atar veya Claude üretir
        ↓
[file_watcher.py] algılar
        ↓
[01_scene_setup.py] sahne hazırlar
        ↓
[Claude MCP / template] modeli oluşturur
        ↓
[02_auto_uv.py] UV unwrap + seam
        ↓
[03_auto_texture.py] PBR materyal atar
        ↓
[04_qa_check.py] kalite kontrol
        ↓
  PASS? ──→ [05_batch_export.py] → exports/fbx/ + exports/glb/ + thumbnail
  FAIL? ──→ _review/ klasörüne taşı, log'a yaz
```
