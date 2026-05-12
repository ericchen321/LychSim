# Roadmap and Releases

## Roadmap

- [ ] Release external scene layout support
- [ ] Release the full [`wufeim/lychsim_scenes`](https://huggingface.co/datasets/wufeim/lychsim_scenes) dataset
- [ ] Release the full [`wufeim/lychsim_objects`](https://huggingface.co/datasets/wufeim/lychsim_objects) dataset

## Releases

### v1.0.0 — Public Release

The first public release of LychSim, bundling the Python API, MCP server, `lychsim` CLI, and the public annotation datasets into a single installable package.

- **Python API** (`lychsim.api.LychSim`) for cameras, objects, and procedural-rule queries against a running Unreal Engine instance via the [UnrealCV](https://unrealcv.org/) plugin.
- **Camera capture**: RGB, depth, surface normals, instance / semantic segmentation, and z-buffer.
- **Object manipulation**: list, query bounding boxes (AABB / OBB / bounds), update locations and rotations, add and delete actors.
- **MCP server** (`lychsim.mcp`) exposing the same API over stdio so LLM clients (Claude Code, Claude Desktop, …) can read and act on a live scene.
- **`lychsim` CLI** for project registration, detached background launches, instance inspection (`ps` / `logs` / `stop`), and configuration sanity-checks (`doctor`).
- **Public annotation datasets** on the Hugging Face Hub:
  - [`wufeim/lychsim_objects`](https://huggingface.co/datasets/wufeim/lychsim_objects) — per-asset semantic category, canonical scale, pose alignment, and precomputed `mesh_offset` for bottom-center spawning.
  - [`wufeim/lychsim_scenes`](https://huggingface.co/datasets/wufeim/lychsim_scenes) — scene-level procedural rules (navigable floor spaces, road areas, pedestrian walks, pedestrian / vehicle trajectories).
- **Full documentation** with tutorials and API reference at [wufeim.github.io/LychSim](https://wufeim.github.io/LychSim/).
