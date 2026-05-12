"""``lychsim capture`` -- snapshot a running scene's visuals and annotations to disk.

Pauses the simulation (so physics / animations don't drift between requests),
captures the standard outputs (lit, segmentation, depth, normal, point map)
plus per-object and camera annotation JSON, then resumes. Files are written
into the requested output directory:

    output_dir/
        lit.png
        seg.png
        depth.npy
        normal.png
        object_annots.json
        camera_annots.json

The camera annotations JSON is augmented with an ``fxfycxcy`` intrinsics
field derived from the FOV / film size, mirroring the helper used in the
data-collection notebooks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from ...api import LychSim


HELP = "Capture a snapshot from a running LychSim instance."


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "output_dir", type=Path,
        help="Directory to write the snapshot into. Created if missing.",
    )
    parser.add_argument(
        "--host", default="localhost",
        help="LychSim server host (default: localhost).",
    )
    parser.add_argument(
        "--port", type=int, default=9000,
        help="LychSim server port (default: 9000).",
    )
    parser.add_argument(
        "--cam-id", type=int, default=0,
        help="Camera ID to capture from (default: 0).",
    )
    parser.add_argument(
        "--width", type=int, default=1920,
        help="Capture width in pixels (default: 1920). Resizes camera 0's film size.",
    )
    parser.add_argument(
        "--height", type=int, default=1080,
        help="Capture height in pixels (default: 1080).",
    )
    parser.add_argument(
        "--warmup", type=int, default=100,
        help="Camera warmup steps before the lit capture (default: 100).",
    )
    parser.add_argument(
        "--no-pause", action="store_true",
        help="Skip pause/resume around the capture.",
    )


def _augment_intrinsics(cam_annots: dict) -> None:
    """Mutate cam_annots in-place to add fxfycxcy on the first camera output."""
    outputs = cam_annots.get("outputs") or []
    if not outputs:
        return
    entry = outputs[0]
    fov = entry.get("fov")
    w = entry.get("width")
    h = entry.get("height")
    if fov is None or w is None or h is None:
        return
    fovx = np.deg2rad(fov)
    fx = 0.5 * w / np.tan(0.5 * fovx)
    fovy = 2.0 * np.arctan((h / float(w)) * np.tan(0.5 * fovx))
    fy = 0.5 * h / np.tan(0.5 * fovy)
    entry["fxfycxcy"] = [fx, fy, w / 2.0, h / 2.0]


def run(args: argparse.Namespace) -> int:
    args.output_dir.mkdir(parents=True, exist_ok=True)

    sim = LychSim(
        server_name=args.host, port=args.port,
        width=args.width, height=args.height,
    )

    paused = False
    try:
        if not args.no_pause:
            sim.pause()
            paused = True

        lit = sim.get_cam_lit(args.cam_id, warmup=args.warmup)
        lit.save(args.output_dir / "lit.png")

        seg = sim.get_cam_seg(args.cam_id)
        seg.save(args.output_dir / "seg.png")

        depth = sim.get_cam_depth(args.cam_id)
        np.save(args.output_dir / "depth.npy", depth)

        normal = sim.get_cam_normal(args.cam_id)
        normal.save(args.output_dir / "normal.png")

        obj_annots = sim.get_obj_annots()
        with (args.output_dir / "object_annots.json").open("w", encoding="utf-8") as f:
            json.dump(obj_annots, f, indent=2)

        cam_annots = sim.get_cam_annots(args.cam_id)
        _augment_intrinsics(cam_annots)
        with (args.output_dir / "camera_annots.json").open("w", encoding="utf-8") as f:
            json.dump(cam_annots, f, indent=2)

        print(f"[lychsim capture] saved snapshot to {args.output_dir.resolve()}")
        return 0
    finally:
        if paused:
            try:
                sim.resume()
            except Exception as e:
                print(f"[lychsim capture] warning: resume() failed: {e}")
        sim.close()
