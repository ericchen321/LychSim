---
name: plan_scene
description: Plan and place furniture in a LychSim Unreal Engine scene from a high-level scene spec (assets, room geometry, layout requirements). Iterates by querying the scene, placing objects, and verifying visually with camera screenshots.
---

# Plan Scene

Use this skill when the user asks to "lay out", "furnish", "plan", "set up", or "decorate" a LychSim scene from a markdown specification file.

## Input

The user provides a **scene spec** (markdown file) containing:

- **Assets** -- a list of object names and their Unreal Engine asset paths.
- **Room Geometry** -- floor corners or bounding box defining the room's X/Y/Z ranges and floor Z level.
- **Layout Requirements** -- what to place: counts, groupings, stacking relationships, and scale overrides.
- **Placement Options** -- `collision_handling`, `skip_existing`, `clear_scene_first`, `lock_rotation`.
- **Style Notes** (optional) -- qualitative guidance on arrangement, spacing, and aesthetics.
- **Final Camera Pose** (optional) -- included for reference but **do not act on it**; the camera is managed externally.

## Expected Output

A fully placed scene matching the spec, verified visually via camera screenshots. The assistant should:

1. Place all objects listed in the layout requirements with correct positions, rotations, and scales.
2. Respect stacking relationships (e.g. objects "on top of" a table use the table's height).
3. Avoid collisions and maintain walkway clearances described in style notes.
4. Visually verify the result and self-correct any issues (overlaps, wrong-facing furniture, floating objects).
5. Capture a final `get_camera_lit` screenshot to confirm the result.

## Available MCP Tools

- **State queries**: `list_objects`, `get_object_location`, `get_object_rotation`, `get_camera_location`, `get_camera_rotation`
- **Spawning / editing**: `add_object`, `set_object_location`, `set_object_rotation`, `update_object`, `delete_object`
- **Sizing**: `get_mesh_extent` -- returns half-extents `[x, y, z]` for an asset path. Full dimension = 2x the extent. May return `[0,0,0]` for some blueprint assets; fall back to visual estimation in that case.
- **Camera**: `get_camera_lit` only. **Do NOT call `set_camera_location` or `set_camera_rotation`** -- the camera is managed externally and must not be moved or rotated by this skill.

## Workflow

1. **Read the spec.** Parse asset paths, room geometry, layout requirements, placement options, and style notes.

2. **Snapshot the current state.** Call `list_objects` to see what already exists, then capture a camera image with `get_camera_lit`. The scene is rarely empty -- there are usually persistent props you should not delete unless `clear_scene_first` is true.

3. **Plan zones.** Organize the layout into functional zones (e.g. seating area, work area, reading corner) before computing coordinates. Functional groupings produce more realistic scenes than scattered placement.

4. **Place anchors first.** Spawn the largest objects that define each zone before placing smaller items on or around them.

5. **Stack using mesh extents.** For objects that sit on top of other objects, query `get_mesh_extent` on the supporting object's asset path to compute the correct Z offset. If the extent query fails, estimate based on typical furniture dimensions.

6. **Orient furniture deliberately.** Mesh forward direction varies by asset -- do not assume a convention. Verify chair/sofa facing with a camera screenshot and adjust if wrong.

7. **Verify visually.** Capture `get_camera_lit` to check the scene from the current camera angle. Look for overlaps, wrong-facing furniture, floating objects, or items placed inside other objects.

8. **Iterate.** Fix any issues found in the screenshot. Self-correct until the scene looks correct.

## Coordinate System

- Units: centimeters.
- Left-handed, Z-up.
- `yaw=0` -> forward = +X. `yaw=90` -> +Y. `yaw=-90` -> -Y. `yaw=180` -> -X.
- Rotation order: `[pitch, yaw, roll]` in degrees.

## Placement Options

Map the spec's placement options to `add_object` arguments:

| Spec key             | How to apply                                                      |
|----------------------|-------------------------------------------------------------------|
| `collision_handling` | Pass directly to `add_object` (e.g. `adjust_if_possible`)        |
| `skip_existing`      | Call `list_objects` first; skip IDs already in the scene          |
| `clear_scene_first`  | If true, delete objects you previously spawned, not scene props   |
| `lock_rotation`      | Pass to `add_object` as `lock_rotation`                           |

## Camera

The camera position and rotation are managed externally. **Never move or rotate the camera.** Only use `get_camera_lit` to capture screenshots from the current viewpoint.
