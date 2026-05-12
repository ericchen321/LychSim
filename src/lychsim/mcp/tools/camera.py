"""Camera capture and control tools."""

from __future__ import annotations

import io
from typing import Optional

from mcp.server.fastmcp import Image as MCPImage

from ..server import get_sim, mcp


@mcp.tool()
def get_camera_lit(cam_id: int = 0) -> MCPImage:
    """Capture an RGB (lit) image from a scene camera.

    Arguments:
        cam_id: Camera index. The default camera is ``0``.

    Returns:
        A PNG image of the current camera view. Use this to see the
        scene, verify object placement, or inspect lighting.
    """
    pil_img = get_sim().get_cam_lit(cam_id=cam_id)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return MCPImage(data=buf.getvalue(), format="png")


@mcp.tool()
def get_camera_location(cam_id: int = 0) -> list[float]:
    """Get the world-space position of a scene camera.

    Arguments:
        cam_id: Camera index. The default camera is ``0``.

    Returns:
        ``[x, y, z]`` in centimeters (left-handed, Z-up).
    """
    return get_sim().get_cam_loc(cam_id)


@mcp.tool()
def get_camera_rotation(cam_id: int = 0) -> list[float]:
    """Get the rotation of a scene camera.

    Arguments:
        cam_id: Camera index. The default camera is ``0``.

    Returns:
        ``[pitch, yaw, roll]`` in degrees.
    """
    return get_sim().get_cam_rot(cam_id)


@mcp.tool()
def set_camera_location(location: list[float], cam_id: int = 0) -> str:
    """Move a scene camera to a new world-space position.

    Arguments:
        location: Target ``[x, y, z]`` in centimeters (left-handed,
            Z-up). For example ``[500, -100, 200]`` places the camera
            roughly in the centre of a typical LoftOffice scene at
            eye height.
        cam_id: Camera index. The default camera is ``0``.

    Returns:
        ``"ok"`` on success.
    """
    get_sim().set_cam_loc(cam_id, location)
    return "ok"


@mcp.tool()
def set_camera_rotation(rotation: list[float], cam_id: int = 0) -> str:
    """Set the rotation of a scene camera.

    Arguments:
        rotation: ``[pitch, yaw, roll]`` in degrees.

            - **pitch** — look up (positive) / down (negative).
            - **yaw** — turn right (positive) / left (negative).
            - **roll** — tilt clockwise (positive).

            Example: ``[-15, 90, 0]`` points the camera slightly
            downward and facing along the +Y axis.
        cam_id: Camera index. The default camera is ``0``.

    Returns:
        ``"ok"`` on success.
    """
    get_sim().set_cam_rot(cam_id, rotation)
    return "ok"
