"""Probe each asset in a CSV and record its mesh extent + spawn offset.

For every row in the input CSV, this script:

1. Spawns the asset at world origin (rot=0, scale=1) with a temporary ID.
2. Reads the mesh extent (half-sizes from the static-mesh asset).
3. Reads the actor AABB (world-space, axis-aligned) and derives the spawn
   offset needed so that the bottom-center of the placed bbox lands on the
   requested spawn location.
4. Deletes the temporary actor.
5. Writes an augmented CSV with six extra columns.

Bounds source: we use ``get_obj_obb`` because in the current C++ plugin it
maps to ``AActor::GetActorBounds(bOnlyCollidingComponents=false, ...)``,
which aggregates *every* registered primitive component (including
non-colliding visual meshes). That's what we want for visual-bbox
alignment. ``get_obj_aabb`` in contrast calls
``FActorController::GetAxisAlignedBoundingBox()`` which typically reflects
only the root/collision primitive and understates BP composites like
``BP_Tv_stand`` or ``BP_Dresser_*``. Since we spawn the probe at rotation
(0,0,0), the OBB's world-axis extent is identical to a true AABB.

Run:
    python scripts/compute_spawn_offsets.py \
        C:\\Users\\mawuf\\Documents\\research\\LychSimMCP\\lychsim_objs.csv

Env vars ``LYCHSIM_HOST`` / ``LYCHSIM_PORT`` override the default
``localhost:9000``.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

from lychsim.api import LychSim
from tqdm import tqdm


EXTRA_COLUMNS = [
    "mesh_extent_x", "mesh_extent_y", "mesh_extent_z",
    "spawn_offset_x", "spawn_offset_y", "spawn_offset_z",
]


def probe_asset(sim: LychSim, asset_path: str, probe_id: str) -> dict:
    """Spawn at origin, read extents, delete. Return the six extra fields."""
    sim.add_obj(
        obj_id=probe_id,
        obj_path=asset_path,
        loc=[0.0, 0.0, 0.0],
        rot=[0.0, 0.0, 0.0],
        scale=1.0,
    )
    try:
        mesh_res = sim.get_mesh_extent(probe_id)
        mesh_extent = mesh_res["outputs"][0].get("extent", [0.0, 0.0, 0.0])

        # get_obj_obb -> (center[3], extent_rot[6]); extent is [0:3].
        # At probe rotation (0,0,0) this equals GetActorBounds(false).
        center, extent_rot = sim.get_obj_obb(probe_id)
        cx, cy, cz = float(center[0]), float(center[1]), float(center[2])
        ez = float(extent_rot[2])

        # Spawned at origin, bottom-center of the actor bbox sits at
        # (cx, cy, cz - ez). To make a future spawn land its bottom-center
        # at an arbitrary (X, Y, Z), pass location = (X, Y, Z) + offset
        # where offset = -bottom_center_when_origin_spawned.
        offset = (-cx, -cy, -(cz - ez))
    finally:
        try:
            sim.del_obj(probe_id)
        except Exception:
            pass

    return {
        "mesh_extent_x": mesh_extent[0],
        "mesh_extent_y": mesh_extent[1],
        "mesh_extent_z": mesh_extent[2],
        "spawn_offset_x": offset[0],
        "spawn_offset_y": offset[1],
        "spawn_offset_z": offset[2],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input_csv", type=Path)
    ap.add_argument("--output_csv", type=Path, default=None,
                    help="Output CSV (default: <input>_with_offsets.csv)")
    ap.add_argument("--path-column", default="object_path")
    args = ap.parse_args()

    out_path = args.output_csv or args.input_csv.with_name(
        args.input_csv.stem + "_with_offsets.csv"
    )

    host = os.environ.get("LYCHSIM_HOST", "localhost")
    port = int(os.environ.get("LYCHSIM_PORT", "9000"))
    sim = LychSim(server_name=host, port=port)

    with args.input_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    for col in EXTRA_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    pbar = tqdm(rows, desc="probing assets", unit="obj")
    n_ok = n_skip = n_fail = 0
    try:
        for i, row in enumerate(pbar):
            asset_path = (row.get(args.path_column) or "").strip()
            if not asset_path:
                n_skip += 1
                pbar.set_postfix(ok=n_ok, skip=n_skip, fail=n_fail)
                for col in EXTRA_COLUMNS:
                    row.setdefault(col, "")
                continue

            probe_id = f"__probe_{i}_{int(time.time() * 1000) & 0xFFFF}"
            try:
                extra = probe_asset(sim, asset_path, probe_id)
                row.update({k: f"{v:.4f}" for k, v in extra.items()})
                n_ok += 1
            except Exception as e:
                tqdm.write(f"[{i}] FAIL {asset_path}: {e}")
                n_fail += 1
                for col in EXTRA_COLUMNS:
                    row.setdefault(col, "")
            pbar.set_postfix(ok=n_ok, skip=n_skip, fail=n_fail)
    finally:
        pbar.close()
        sim.close()

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
