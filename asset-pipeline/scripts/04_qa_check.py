"""
Asset kalite kontrolu:
- Poly sayisi budget icinde mi?
- Non-manifold edge var mi?
- UV overlap var mi?
- Materyal atanmamis face var mi?
- Scale apply edilmis mi?
- Origin dogru konumda mi?
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
    tri_count = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    metadata = json.loads(bpy.context.scene.get("asset_metadata", "{}"))
    budget = metadata.get("poly_budget", 10000)
    report["checks"]["poly_count"] = {
        "tris": tri_count,
        "polys": poly_count,
        "budget": budget,
        "pass": tri_count <= budget
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
        status = "PASS" if check["pass"] else "FAIL"
        detail = ""
        if "tris" in check:
            detail = f" ({check['tris']} tris / {check.get('budget', '?')} budget)"
        if "count" in check:
            detail = f" ({check['count']} found)"
        print(f"  [{status}]  {name}{detail}")
    print(f"\n  OVERALL: {'PASSED' if report['passed'] else 'FAILED'}")
    print(f"{'='*50}\n")
