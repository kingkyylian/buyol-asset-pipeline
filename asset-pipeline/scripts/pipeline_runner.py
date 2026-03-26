"""
pipeline_runner.py — Tek komutla tum pipeline'i calistirir

Kullanim:
  blender --background --python pipeline_runner.py -- --asset sword --category weapon
"""

import sys
import os
import json
from datetime import datetime

# Script dizinini path'e ekle
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from importlib import import_module


def run_pipeline(asset_name, category, material_map=None):
    log = []

    # Lazy imports (Blender icinde calistirilacak)
    scene_setup = import_module("01_scene_setup")
    auto_uv = import_module("02_auto_uv")
    auto_texture = import_module("03_auto_texture")
    qa_check = import_module("04_qa_check")
    batch_export = import_module("05_batch_export")

    # 1. Sahne hazirla
    log.append(f"[{timestamp()}] Setting up scene for {asset_name}")
    metadata = scene_setup.setup_scene(asset_name, category)

    # 2. Model zaten hazirsa (manuel veya AI ile uretilmis)
    log.append(f"[{timestamp()}] Model expected in scene")

    # 3. UV Unwrap
    log.append(f"[{timestamp()}] Running auto UV unwrap")
    uv_result = auto_uv.auto_uv_unwrap(asset_name)
    log.append(f"[{timestamp()}] UV result: {uv_result}")

    # 4. Texture
    if material_map:
        log.append(f"[{timestamp()}] Assigning materials")
        auto_texture.auto_assign_materials(asset_name, material_map)

    # 5. QA Check
    log.append(f"[{timestamp()}] Running QA check")
    qa = qa_check.run_qa_check(asset_name)
    qa_check.print_qa_report(qa)

    if not qa["passed"]:
        log.append(f"[{timestamp()}] QA FAILED - asset not exported")
        return {"status": "failed", "qa": qa, "log": log}

    # 6. Export
    log.append(f"[{timestamp()}] Exporting")
    exports = batch_export.batch_export(asset_name)

    # 7. Log
    log.append(f"[{timestamp()}] Pipeline complete")

    return {"status": "success", "qa": qa, "exports": exports, "log": log}


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


if __name__ == "__main__":
    # CLI argumanlari
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]

    asset_name = "unnamed"
    category = "prop"

    for i, arg in enumerate(argv):
        if arg == "--asset" and i + 1 < len(argv):
            asset_name = argv[i + 1]
        elif arg == "--category" and i + 1 < len(argv):
            category = argv[i + 1]

    result = run_pipeline(asset_name, category)
    print(json.dumps(result, indent=2, default=str))
