"""Object tools — query, spawn, move, and delete."""

from __future__ import annotations

from typing import Optional

from ..server import get_sim, mcp


@mcp.tool()
def list_objects() -> list[str]:
    """List the IDs of every object currently in the LychSim scene.

    Returns a list of object ID strings. These IDs are what the other
    ``*_object_*`` tools accept as the ``obj_id`` argument.
    """
    return get_sim().get_obj_list()


@mcp.tool()
def get_object_location(obj_ids: Optional[list[str]] = None) -> dict:
    """Get the world-space locations of one, several, or all objects.

    Arguments:
        obj_ids: A list of object IDs (as returned by ``list_objects``).
            Pass a single-element list to query one object, multiple
            elements to batch-query several, or omit the argument
            entirely to query every object in the scene.

    Returns:
        A dict with the shape::

            {
                "status": "ok" | "partial" | "none",
                "error":  "<readable message>",   # only when status != "ok"
                "outputs": [
                    {"object_id": str,
                     "status": "ok" | "not_found",
                     "location": [x, y, z]},      # omitted on not_found
                    ...
                ]
            }

        Top-level ``status`` is ``"ok"`` when every requested object
        resolved, ``"none"`` when none did, and ``"partial"`` for a
        mix; the ``error`` field carries a human-readable summary in
        the latter two cases. Locations are in Unreal world
        coordinates (centimeters, left-handed, Z-up).
    """
    return get_sim().get_obj_loc(obj_ids)


@mcp.tool()
def add_object(
    obj_id: str,
    obj_path: str,
    location: Optional[list[float]] = None,
    rotation: Optional[list[float]] = None,
    scale: float = 1.0,
    collision_handling: str = "default",
    lock_rotation: bool = False,
) -> dict:
    """Spawn a new object into the LychSim scene.

    Arguments:
        obj_id: A unique name for the new object (e.g. ``"Table_1"``).
            Must not collide with an existing object ID in the scene —
            call ``list_objects`` first to check.
        obj_path: Unreal Engine asset path for the mesh or blueprint to
            spawn (e.g. ``"/Game/Assets/Mesh/SM_Table"``). Use
            ``list_objects`` + ``get_object_location`` to inspect what
            is already in the scene, but asset paths come from the
            project's Content directory, not from scene queries.
        location: World-space ``[x, y, z]`` in centimeters
            (left-handed, Z-up). Defaults to the world origin
            ``[0, 0, 0]``.
        rotation: ``[pitch, yaw, roll]`` in degrees. Defaults to
            ``[0, 0, 0]``.
        scale: Uniform scale factor. Defaults to ``1.0``.
        collision_handling: How to handle spawn-time collisions.
            ``"default"`` — always spawn;
            ``"skip_if_colliding"`` — do not spawn if the location
            overlaps existing geometry;
            ``"adjust_if_possible"`` — try to nudge the object to a
            free spot, but fail if none is found.
        lock_rotation: If ``true``, lock the actor's rotation after
            spawning (useful for static props).

    Returns:
        ``{"status": "ok"}`` on success, or
        ``{"status": "<error_code>"}`` describing what went wrong
        (e.g. ``"object_with_same_name_already_exists"``,
        ``"failed_to_spawn_actor"``, ``"unknown_argument_format"``).
    """
    loc = location or [0.0, 0.0, 0.0]
    rot = rotation or [0.0, 0.0, 0.0]

    return get_sim().add_obj(
        obj_id=obj_id,
        obj_path=obj_path,
        loc=loc,
        rot=rot,
        scale=scale,
        skip_if_colliding=(collision_handling == "skip_if_colliding"),
        adjust_if_possible=(collision_handling == "adjust_if_possible"),
        lock_rotation=lock_rotation,
    )


@mcp.tool()
def update_object(
    obj_id: str,
    location: Optional[list[float]] = None,
    rotation: Optional[list[float]] = None,
) -> str:
    """Move and/or rotate an existing object in the scene.

    Use this to reposition objects after spawning them, or to adjust a
    layout iteratively. Call ``get_camera_lit`` afterwards to verify the
    result visually.

    Arguments:
        obj_id: The object to update (as returned by ``list_objects``).
        location: New world-space ``[x, y, z]`` in centimeters
            (left-handed, Z-up). Omit to keep the current position.
        rotation: New ``[pitch, yaw, roll]`` in degrees. Omit to keep
            the current rotation.

    At least one of ``location`` or ``rotation`` must be provided.

    Returns:
        ``"ok"`` on success.
    """
    get_sim().update_obj(obj_id, loc=location, rot=rotation)
    return "ok"


@mcp.tool()
def set_object_location(obj_id: str, location: list[float]) -> str:
    """Set the world-space position of an existing object.

    Arguments:
        obj_id: The object to move (as returned by ``list_objects``).
        location: New ``[x, y, z]`` in centimeters (left-handed, Z-up).

    Returns:
        ``"ok"`` on success.
    """
    get_sim().update_obj(obj_id, loc=location)
    return "ok"


@mcp.tool()
def set_object_rotation(obj_id: str, rotation: list[float]) -> str:
    """Set the world-space rotation of an existing object.

    Arguments:
        obj_id: The object to rotate (as returned by ``list_objects``).
        rotation: New ``[pitch, yaw, roll]`` in degrees.

    Returns:
        ``"ok"`` on success.
    """
    get_sim().update_obj(obj_id, rot=rotation)
    return "ok"


@mcp.tool()
def delete_object(obj_id: str) -> str:
    """Remove an object from the scene.

    Arguments:
        obj_id: The object to delete (as returned by ``list_objects``).

    Returns:
        ``"ok"`` on success.
    """
    get_sim().del_obj(obj_id)
    return "ok"


@mcp.tool()
def get_mesh_extent(obj_ids: list[str]) -> dict:
    """Get the 3D mesh extents (bounding box dimensions) of one or more objects.

    This is useful for computing placement offsets — for example, to
    place a monitor on top of a table, query the table's extent to
    learn its height, then set the monitor's Z to
    ``table_z + table_extent_z / 2``.

    Arguments:
        obj_ids: One or more object IDs (as returned by ``list_objects``).

    Returns:
        A dict with per-object entries containing the mesh extent
        ``[x, y, z]`` in centimeters — the full width, depth, and
        height of the object's bounding box.
    """
    if len(obj_ids) == 1:
        return get_sim().get_mesh_extent(obj_ids[0])
    return get_sim().get_mesh_extent(obj_ids)


@mcp.tool()
def get_object_rotation(obj_ids: Optional[list[str]] = None) -> dict:
    """Get the world-space rotations of one, several, or all objects.

    Arguments:
        obj_ids: A list of object IDs (as returned by ``list_objects``).
            Pass a single-element list to query one object, multiple
            elements to batch-query several, or omit the argument
            entirely to query every object in the scene.

    Returns:
        A dict with the shape::

            {
                "status": "ok" | "partial" | "none",
                "error":  "<readable message>",   # only when status != "ok"
                "outputs": [
                    {"object_id": str,
                     "status": "ok" | "not_found",
                     "rotation": [pitch, yaw, roll]},  # omitted on not_found
                    ...
                ]
            }

        Top-level ``status`` is ``"ok"`` when every requested object
        resolved, ``"none"`` when none did, and ``"partial"`` for a
        mix; the ``error`` field carries a human-readable summary in
        the latter two cases. Rotations are in degrees
        ``[pitch, yaw, roll]``.
    """
    return get_sim().get_obj_rot(obj_ids)
