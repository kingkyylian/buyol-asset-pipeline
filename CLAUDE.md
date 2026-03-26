# Blender Asset Production Pipeline

## Proje Nedir
Medieval fantasy RPG icin 376 asset (530 varyantli) uretim pipeline'i. Claude, Blender MCP uzerinden dogrudan Blender'da model uretir, texture atar, QA yapar ve export eder.

## Sistem Mimarisi

```
Claude CLI (sen)
  |
  |-- Blender MCP (localhost:9876) --> Blender 5.1
  |     execute_blender_code, get_scene_info, get_viewport_screenshot
  |
  |-- ambientCG API --> PBR texture indirme (CC0, ucretsiz)
  |
  |-- Pipeline Scripts --> UV, materyal, QA, export otomasyonu
```

## Baslangic Kontrol Listesi

Her session basinda:
1. `get_scene_info` ile Blender baglantisini test et
2. Baglanamiyorsan kullaniciya "Blender'da N paneli > BlenderMCP > Connect to MCP server" de
3. Port 9876 acik mi kontrol: `nc -z localhost 9876`

## Asset Uretim Akisi (Tek Asset)

```
1. Sahne temizle + isik/kamera kur
2. Modelle (execute_blender_code ile Python kodu gonder)
3. UV Unwrap (Smart UV Project)
4. Materyal ata (ambientCG texture VEYA procedural preset)
5. QA Check (tri count, non-manifold, scale, UV, material)
6. Export (FBX + GLB + PNG thumbnail)
```

## Blender 5.1 Turkce Uyari

Blender Turkce kurulu. Node isimleri FARKLI:
- "Principled BSDF" --> "Ilkeli BSDF"
- "Material Output" --> "Malzeme Ciktisi"

**ASLA node'u isimle arama.** Type ile bul:
```python
bsdf = None
for n in nodes:
    if n.type == 'BSDF_PRINCIPLED':
        bsdf = n
        break
```

Diger onemli type'lar: `OUTPUT_MATERIAL`, `TEX_IMAGE`, `NORMAL_MAP`, `MAPPING`, `TEX_COORD`, `VALTORGB`, `TEX_NOISE`, `TEX_WAVE`, `BUMP`, `MIX`

Render engine: `BLENDER_EEVEE` (BLENDER_EEVEE_NEXT degil)

MixRGB node Blender 5'te deprecated: `ShaderNodeMix` kullan (`data_type='RGBA'`).

## Modelleme Yaklasimlari

Ben (Claude) primitive'lerden model uretiyorum:
- `bpy.ops.mesh.primitive_cylinder_add()` -- varil, mum, sise
- `bpy.ops.mesh.primitive_cube_add()` -- kasa, masa, sandik
- `bpy.ops.mesh.primitive_uv_sphere_add()` -- top, meyve
- `bpy.ops.mesh.primitive_torus_add()` -- halka, bant
- `bmesh.ops.bisect_plane()` -- loop cut yerine (loopcut_and_slide Blender 5'te yok)
- Vertex manipulasyonu ile sekillendirme (bulge, taper, vb.)

Karmasik modeller (detayli kiliclar, organik formlar) icin kullanici modeller, ben UV + texture + QA + export yaparim.

## Texture Sistemi

### ambientCG (otomatik, tercih edilen)
```bash
python3 asset-pipeline/scripts/ambientcg_downloader.py search "wood oak" --limit 5
python3 asset-pipeline/scripts/ambientcg_downloader.py auto "rusty metal" -r 1K
```
Indirilen dosyalar: `asset-pipeline/textures/library/{AssetID}/`
Icerik: Color.jpg, Roughness.jpg, NormalGL.jpg, Displacement.jpg, AO.jpg, Metalness.jpg

### Procedural Preset'ler
`03_auto_texture.py` icinde hazir preset'ler var:
```python
from scripts.utils.blender_compat import get_principled_bsdf
# Wood: wood_oak, wood_pine, wood_birch, wood_dark, wood_charred
# Metal: iron_dark, iron_rusty, bronze_aged, gold_polished, silver_polished
# Glass: glass_clear, glass_dark_green, glass_brown
# Stone: stone_grey, stone_dark, stone_mossy
# Fabric: burlap, cloth_white, cloth_torn, rope_hemp, leather_brown
```

### Solid Color
```python
create_solid_color_material("wick", "#1a1a1a", roughness=0.9)
```

### PBR Node Baglama Sirasi (tam setup)
```
Texture Coord -> Mapping -> Color.jpg -----> x AO.jpg (Multiply) -> Base Color
                         -> Roughness.jpg -----------------------> Roughness
                         -> NormalGL.jpg -> Normal Map Node ------> Normal (Bump chain)
                         -> Displacement.jpg -> Bump Node ------/
```

## Dosya Yapisi

```
pipeline blender/
  .mcp.json                          # Blender MCP server config
  CLAUDE.md                          # Bu dosya
  asset-pipeline-workflow.md         # 2 haftalik sprint plani (referans)
  asset-katalog-full.md              # 376 asset katalogu (referans)
  asset-queue-batch1.json            # Batch 1: 34 asset tanimi (JSON)
  asset-pipeline/
    config/
      pipeline_config.json           # Merkezi konfigrasyon
    scripts/
      01_scene_setup.py              # Sahne hazirlik (isik, kamera, metadata)
      02_auto_uv.py                  # Otomatik UV unwrap
      03_auto_texture.py             # PBR materyal + procedural preset'ler
      04_qa_check.py                 # Kalite kontrol
      05_batch_export.py             # FBX/GLB/thumbnail export
      pipeline_runner.py             # Orkestrasyon
      ambientcg_downloader.py        # ambientCG API client
      batch_processor.py             # Batch JSON parser + prompt uretici
      texture_bulk_download.py       # Toplu texture indirme
      utils/
        blender_compat.py            # Turkce Blender uyumluluk (type-based node bulma)
    assets/
      _queue/                        # Sirada bekleyen
      _wip/                          # Uzerinde calisilan
      _review/                       # QA bekleyen
      _done/                         # Tamamlanmis
    textures/
      library/                       # Indirilen texture'lar
        Wood049/, WoodFloor051/, Metal053B/   # ambientCG'den indirilenler
        woods/, metals/, stones/, fabrics/    # Organize klasorler
    exports/
      fbx/                           # FBX dosyalari
      glb/                           # GLB dosyalari
      thumbnails/                    # PNG thumbnail render'lar
```

## Batch 1 Asset Listesi (34 asset)

batch_processor.py ile listele:
```bash
python3 asset-pipeline/scripts/batch_processor.py --json asset-queue-batch1.json --list
```

Kategoriler: furniture (6), prop (13), environment (4), nature (6), consumable (4), treasure (1)

Her asset'in JSON tanimi: id, name, category, tri_budget, texture_res, materials[], variants[], export[]

## QA Kontrol Kriterleri

- Tri count <= budget (asset'e gore 200-2500)
- Non-manifold edge = 0
- Scale applied (1.0, 1.0, 1.0)
- Rotation applied (0, 0, 0)
- En az 1 material atanmis
- En az 1 UV layer
- Origin X,Y < 0.01 (merkezde)

## Export Standartlari

- FBX: `use_selection=True, apply_scale_options='FBX_SCALE_ALL', path_mode='COPY', embed_textures=True`
- GLB: `use_selection=True, export_format='GLB', export_apply=True`
- Thumbnail: 1024x1024 PNG, transparent background, EEVEE render

## Bilinen Sorunlar ve Cozumleri

| Sorun | Cozum |
|-------|-------|
| `nodes["Principled BSDF"]` KeyError | Type ile bul: `n.type == 'BSDF_PRINCIPLED'` |
| `BLENDER_EEVEE_NEXT` not found | `BLENDER_EEVEE` kullan |
| `loopcut_and_slide` not found | `bmesh.ops.bisect_plane()` kullan |
| `ShaderNodeMixRGB` deprecated | `ShaderNodeMix` + `data_type='RGBA'` kullan |
| Viewport'ta AO/bump gorunmuyor | `space.shading.type = 'RENDERED'` veya render al |
| Hunyuan3D lokal | Denendi, 16GB Mac'te RAM/kalite sorunu, KURMA |
| Hyper3D Rodin | Ucretli, KULLANMA |

## Ornek: Yeni Asset Uretme (varil ornegi)

```python
# 1. Sahne temizle
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()

# 2. Isik + kamera (01_scene_setup.py'den)
# 3-point lighting + thumbnail camera

# 3. Model olustur
bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.4, depth=1.0, location=(0,0,0.5))
barrel = bpy.context.active_object
barrel.name = "barrel"
# bisect ile loop cut, vertex ile bulge, torus ile metal bant...

# 4. UV
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=66, island_margin=0.02)
bpy.ops.object.mode_set(mode='OBJECT')

# 5. Texture (ambientCG'den indir, node'lara bagla)
# VEYA procedural preset kullan

# 6. QA + Export
```
