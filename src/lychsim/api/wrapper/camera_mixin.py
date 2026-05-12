import io
import json

import numpy as np
from PIL import Image


class CameraCommandsMixin:
    """Mixin for camera-related commands."""

    def _ensure_cam_binary(self, res, cam_id: int, ctx: str) -> bytes:
        """Return raw bytes, or raise a clean error by parsing the JSON envelope.
        Binary-capture handlers return raw png/npy on success; on failure they
        emit the standard {"status": "error", "error": "...", "outputs": []} envelope.
        """
        if isinstance(res, (bytes, bytearray)):
            return bytes(res)
        try:
            env = json.loads(res)
            msg = env.get("error", env)
        except (ValueError, TypeError):
            msg = res
        raise ValueError(f"Failed to {ctx} for camera {cam_id}: {msg}")

    def get_cam_lit(self, cam_id: int, warmup: int = 0, experimental=False) -> Image.Image:
        """Capture a lit RGB image from the given camera.

        Args:
            cam_id: Camera ID.
            warmup: Number of extra render frames to issue before the capture.
                Useful when the scene was just modified and TAA / streaming
                still need a few frames to settle. Default 0.
            experimental: If True, request the experimental rendering path
                (``-experimental``). Default False.

        Returns:
            PIL ``Image`` of the camera view (RGB, decoded from PNG).
        """
        if experimental:
            cmd = f"lych cam get_lit {cam_id} png -warmup={warmup} -experimental"
        else:
            cmd = f"lych cam get_lit {cam_id} png -warmup={warmup}"
        res = self.client.request(cmd)
        data = self._ensure_cam_binary(res, cam_id, "get lit image")
        if data[:8] != b"\x89PNG\r\n\x1a\n":
            preview = data[:200].decode("utf-8", "replace")
            raise ValueError(f"Failed to get lit image for camera {cam_id}: expected PNG, got: {preview!r}")
        return Image.open(io.BytesIO(data))

    def warmup_cam(self, cam_id: int, num_steps: int = 10) -> None:
        """Issue ``num_steps`` no-op render frames to let the camera settle.

        Useful when temporal anti-aliasing or texture streaming would
        otherwise produce a blurry / under-streamed first capture. Cheaper
        than scattering ``warmup=`` arguments across multiple calls.

        Args:
            cam_id: Camera ID.
            num_steps: Number of render frames to issue. Default 10.
        """
        for _ in range(num_steps):
            self.client.request(f"lych cam warmup {cam_id}")

    def get_cam_seg(self, cam_id: int) -> Image.Image:
        """Capture an instance segmentation map from the given camera.

        Each actor in the scene is painted with a unique color (see
        ``get_obj_annots``'s ``color`` field for the per-object color).

        Args:
            cam_id: Camera ID.

        Returns:
            PIL ``Image`` of the segmentation map (RGB, decoded from PNG).
        """
        self.client.request(f"lych cam get_seg {cam_id} png")
        res = self.client.request(f"lych cam get_seg {cam_id} png")
        data = self._ensure_cam_binary(res, cam_id, "get segmentation image")
        return Image.open(io.BytesIO(data))

    def get_cam_ele_seg(self, cam_id: int) -> Image.Image:
        """Capture an element-level segmentation map from the given camera.

        Like ``get_cam_seg`` but at sub-actor granularity (e.g. per
        primitive component within a Blueprint actor).

        Args:
            cam_id: Camera ID.

        Returns:
            PIL ``Image`` of the element segmentation map (RGB).
        """
        self.client.request(f"lych cam get_ele_seg {cam_id} png")
        res = self.client.request(f"lych cam get_ele_seg {cam_id} png")
        data = self._ensure_cam_binary(res, cam_id, "get element segmentation image")
        return Image.open(io.BytesIO(data))

    def get_cam_normal(self, cam_id: int) -> Image.Image:
        """Capture a world-space surface normal map from the given camera.

        Each pixel encodes the surface normal at that hit point in the RGB
        channels (alpha, if present, is dropped).

        Args:
            cam_id: Camera ID.

        Returns:
            PIL ``Image`` of the normal map (RGB).
        """
        self.client.request(f"lych cam get_normal {cam_id} png")
        res = self.client.request(f"lych cam get_normal {cam_id} png")
        data = self._ensure_cam_binary(res, cam_id, "get normal image")
        normal = np.array(Image.open(io.BytesIO(data)))[:, :, :3]
        return Image.fromarray(normal)

    def get_cam_depth(self, cam_id: int) -> np.ndarray:
        """Capture a depth map from the given camera.

        Args:
            cam_id: Camera ID.

        Returns:
            ``np.ndarray`` of shape ``(H, W)`` with depth in centimeters
            (Unreal world units). Out-of-range / sky pixels read 65500+.
        """
        res = self.client.request(f"lych cam get_depth {cam_id} npy")
        data = self._ensure_cam_binary(res, cam_id, "get depth")
        return np.load(io.BytesIO(data))

    def get_cam_zbuffer(self, cam_id: int, obj_ids = None) -> np.ndarray:
        """Capture per-object depth (z-buffer) maps from the given camera.

        Returns a stack of 2D depth maps -- one per requested object --
        useful for occlusion analysis (compare the z-buffer to the depth
        map to find pixels where the object is occluded by something
        nearer the camera).

        Args:
            cam_id: Camera ID.
            obj_ids: Object ID, list of object IDs, or ``None`` /
                empty list for every object in the scene.

        Returns:
            ``np.ndarray`` of shape ``(N, H, W)`` -- one slice per object
            -- with depth in centimeters. Pixels not covered by the
            object read 65500+.
        """
        if isinstance(obj_ids, str):
            obj_ids = [obj_ids]
        if obj_ids is None or len(obj_ids) == 0:
            res = self.client.request(f"lych cam get_zbuffer {cam_id} -all")
        else:
            res = self.client.request(f"lych cam get_zbuffer {cam_id} {' '.join(str(x) for x in obj_ids)}")
        data = self._ensure_cam_binary(res, cam_id, "get z-buffer")
        zbuffer = np.load(io.BytesIO(data))
        if zbuffer.ndim == 2:
            zbuffer = zbuffer[None, ...]
        return zbuffer

    def _parse_cam_envelope(self, res, cam_id: int, field: str):
        env = json.loads(res)
        if env.get("status") != "ok":
            raise ValueError(
                f"Failed to get {field} for camera {cam_id}: {env.get('error', env)}"
            )
        return env["outputs"][0][field]

    def get_cam_loc(self, cam_id: int) -> list:
        """Get camera location in world space.
        Args:
            cam_id (int): Camera ID.
        Returns:
            list: Location as [x, y, z] in world space.
        """
        res = self.client.request(f"lych cam get_loc {cam_id}")
        return self._parse_cam_envelope(res, cam_id, "location")

    def get_cam_rot(self, cam_id: int) -> list:
        """Get camera rotation in world space.
        Args:
            cam_id (int): Camera ID.
        Returns:
            list: Rotation as [pitch, yaw, roll] in degrees.
        """
        res = self.client.request(f"lych cam get_rot {cam_id}")
        return self._parse_cam_envelope(res, cam_id, "rotation")

    def set_cam_loc(self, cam_id: int, loc: list | np.ndarray) -> dict:
        """Set camera location in world space.
        Args:
            cam_id (int): Camera ID.
            loc (list | np.ndarray): Location as [x, y, z].
        Returns:
            dict: Response envelope with ``status`` ("ok" or "error") and
            ``outputs`` (empty on success). Includes ``error`` message on failure.
        """
        if isinstance(loc, np.ndarray):
            loc = loc.tolist()
        loc_str = " ".join(map(str, loc))
        res = self.client.request(f"lych cam set_loc {cam_id} {loc_str}")
        return json.loads(res)

    def set_cam_rot(self, cam_id: int, rot: list | np.ndarray) -> dict:
        """Set camera rotation in world space.
        Args:
            cam_id (int): Camera ID.
            rot (list | np.ndarray): Rotation as [pitch, yaw, roll] in degrees.
        Returns:
            dict: Response envelope with ``status`` ("ok" or "error") and
            ``outputs`` (empty on success). Includes ``error`` message on failure.
        """
        if isinstance(rot, np.ndarray):
            rot = rot.tolist()
        rot_str = " ".join(map(str, rot))
        res = self.client.request(f"lych cam set_rot {cam_id} {rot_str}")
        return json.loads(res)

    def is_cam_pose_invalid(
        self, cam_id: int, loc: list | np.ndarray, radius_cm: float = 5.0
    ) -> bool:
        """Check whether a camera location is in invalid space by overlap testing.
        Args:
            cam_id (int): Camera ID.
            loc (list | np.ndarray): Location as [x, y, z] in world space.
            radius_cm (float): Safety sphere radius in centimeters. Default is 5.0.
        Returns:
            bool: True if pose is invalid (collision/inside), else False.
        """
        if isinstance(loc, np.ndarray):
            loc = loc.tolist()
        if len(loc) != 3:
            raise ValueError(f"loc must have 3 values [x, y, z], got {loc}")

        loc_str = " ".join(map(str, loc))
        res = self.client.request(
            f"lych cam is_pose_invalid {cam_id} {loc_str} {float(radius_cm)}"
        )
        return bool(self._parse_cam_envelope(res, cam_id, "invalid"))

    def get_cam_c2w(self, cam_id: int) -> np.ndarray:
        """Get camera-to-world transformation matrix.
        Args:
            cam_id (int): Camera ID.
        Returns:
            np.ndarray: Camera-to-world transformation matrix.
        """
        res = self.client.request(f"lych cam get_c2w {cam_id}")
        return np.array(self._parse_cam_envelope(res, cam_id, "c2w"), dtype=float)

    def get_cam_fov(self, cam_id: int) -> float:
        """Get camera horizontal field of view in degrees.
        Args:
            cam_id (int): Camera ID.
        Returns:
            float: Horizontal field of view in degrees.
        """
        res = self.client.request(f"lych cam get_fov {cam_id}")
        return float(self._parse_cam_envelope(res, cam_id, "fov"))

    def get_cam_annots(self, cam_id: int) -> dict:
        """Get full per-camera annotations (pose, intrinsics, film size).

        Args:
            cam_id: Camera ID.

        Returns:
            Raw JSON envelope ``{"status", "outputs": [...]}`` with the
            requested camera under ``outputs[0]``. Fields include
            ``location``, ``rotation``, ``fov``, ``c2w``, ``width``,
            ``height``. Convenience wrappers (``get_cam_loc`` etc.)
            return individual fields.
        """
        res = self.client.request(f"lych cam get_annots {cam_id}")
        return json.loads(res)

    def clear_annot_comps(self) -> dict:
        """Clear cached annotation components on the C++ side.

        Returns:
            Raw JSON envelope with ``status``.
        """
        return json.loads(self.client.request("lych cam clear_annot_comps"))

    def get_cam_pointmap(self, cam_id: int, space: str = "all") -> dict[str, np.ndarray]:
        """Get point map in requested spaces.

        Args:
            cam_id: Camera ID.
            space: One of {"camera", "world", "opencv", "all"}; "all" returns all three concatenated.

        Returns:
            Dictionary with keys for each requested space. Each value is a float32 array shaped (H, W, 3).
        """
        res = self.client.request(f"lych cam get_pointmap {cam_id} npy -space={space}")
        data = self._ensure_cam_binary(res, cam_id, "get point map")
        arr = np.load(io.BytesIO(data))
        if arr.ndim != 3 or arr.shape[2] not in (3, 6, 9):
            raise ValueError(f"Unexpected point map shape: {arr.shape}")

        outputs: dict[str, np.ndarray] = {}
        channel_offset = 0

        def _slice(name: str) -> None:
            nonlocal channel_offset
            outputs[name] = arr[:, :, channel_offset:channel_offset+3]
            channel_offset += 3

        # Order matches C++: camera -> world -> opencv
        if space in ("camera", "all"):
            _slice("camera")
        if space in ("world", "all"):
            _slice("world")
        if space in ("opencv", "all"):
            _slice("opencv")

        return outputs
