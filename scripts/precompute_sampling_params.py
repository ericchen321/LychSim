"""Precompute sampling params (mesh extent + spawn offset) for every object in a CSV.

For every row in the input CSV, this script:

1. Spawns the asset at world origin with rotation ``[0, calibration_yaw, 0]``
   and the CSV-supplied ``scale``.
2. Reads the actor's ``bounds`` (= ``Actor->GetActorBounds(false, ...)`` —
   see ``CLAUDE.md`` for why this is preferred over ``bounds_tight``).
3. Records six new columns:

       mesh_extent_{x,y,z}  -- bbox half-sizes (cm)
       mesh_offset_{x,y,z}  -- (-cx, -cy, ez - cz)

   At spawn time, placing the actor at ``loc + mesh_offset`` (same yaw and
   scale) makes the bbox bottom-center land on ``loc``.
4. Deletes the probe actor.

Existing values for the six columns are overwritten on every run. Rows whose
probe fails (asset can't load, degenerate bbox, etc.) get empty cells and a
warning; re-run after the upstream issue is fixed.

Run::

    python scripts/precompute_sampling_params.py lychsim_objects.csv

    # Write to a new file instead of overwriting in place:
    python scripts/precompute_sampling_params.py lychsim_objects.csv \\
        --output lychsim_objects_with_params.csv

Env: requires a running LychSim/UnrealCV server (default ``localhost:9000``).
"""

from __future__ import annotations

import argparse
import csv
import uuid
from pathlib import Path

from lychsim.api import LychSim
from tqdm import tqdm


NEW_COLUMNS = [
    "mesh_extent_x", "mesh_extent_y", "mesh_extent_z",
    "mesh_offset_x", "mesh_offset_y", "mesh_offset_z",
]
BOUNDS_KEY = "bounds"
DEGENERATE_TOL = 1e-3  # cm


def random_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def parse_float(v, default: float) -> float:
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


def probe(sim: LychSim, obj_path: str, yaw: float, scale: float) -> tuple[dict | None, str | None]:
    """Spawn at origin, read bounds, compute extent+offset.

    Returns ``(result, None)`` on success, or ``(None, error_msg)`` on failure.
    Always cleans up the probe actor.
    """
    probe_id = random_id("probe")
    added = False
    try:
        try:
            sim.add_obj(probe_id, obj_path, [0.0, 0.0, 0.0], [0.0, yaw, 0.0], scale)
            added = True
        except Exception as e:
            return None, f"add_obj failed: {type(e).__name__}: {e}"

        annots = sim.get_obj_annots(probe_id)["outputs"][0]
        if annots.get("status") != "ok":
            return None, f"annots status={annots.get('status')!r}"
        b = annots[BOUNDS_KEY]
        cx, cy, cz = b["center"]
        ex, ey, ez = b["extent"]
        if min(ex, ey, ez) <= DEGENERATE_TOL:
            return None, f"degenerate extent ({ex:.4f}, {ey:.4f}, {ez:.4f})"

        return {
            "mesh_extent_x": ex, "mesh_extent_y": ey, "mesh_extent_z": ez,
            "mesh_offset_x": -cx, "mesh_offset_y": -cy, "mesh_offset_z": ez - cz,
        }, None
    finally:
        if added:
            try:
                sim.del_obj(probe_id)
            except Exception as e:
                tqdm.write(f"  [warn] del_obj({probe_id}) failed: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("csv_path", type=Path,
                        help="Path to lychsim_objects.csv (must have path/scale/rotation columns).")
    parser.add_argument("--output", type=Path, default=None,
                        help="Output CSV path. Default: overwrite csv_path in place.")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    if not args.csv_path.is_file():
        raise SystemExit(f"Not a file: {args.csv_path}")

    with args.csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not rows:
        raise SystemExit("CSV is empty.")
    for col in NEW_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    sim = LychSim(server_name=args.host, port=args.port)
    n_ok = 0
    failures: list[tuple[str, str]] = []
    try:
        for row in tqdm(rows, desc="probing"):
            obj_path = row["path"]
            yaw = parse_float(row.get("rotation"), 0.0)
            scale = parse_float(row.get("scale"), 1.0)
            result, err = probe(sim, obj_path, yaw, scale)
            if result is None:
                failures.append((obj_path, err or "unknown"))
                tqdm.write(f"  [fail] {obj_path}: {err}")
                for col in NEW_COLUMNS:
                    row[col] = ""
                continue
            for col in NEW_COLUMNS:
                row[col] = f"{result[col]:.4f}"
            n_ok += 1
    finally:
        sim.close()

    out_path = args.output or args.csv_path
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {out_path}: {n_ok} ok, {len(failures)} failed (of {len(rows)}).")
    if failures:
        print("Failed rows (re-run after fixing upstream):")
        for path, err in failures:
            print(f"  {path}: {err}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
