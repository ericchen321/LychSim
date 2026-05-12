import json
import re

import numpy as np


class ObjectCommandsMixin:
    """Mixin for object-related commands."""

    def get_obj_list(self) -> list[str]:
        """List every actor ID currently in the scene.

        Returns:
            List of object IDs (Unreal actor labels), one per actor.
        """
        res = self.client.request("lych obj list")
        return res.strip().split(" ")

    def get_obj_aabb(self, obj_id: str = None):
        """Get the world-space axis-aligned bounding box for one or all objects.

        Backed by ``FActorController::GetAxisAlignedBoundingBox()``, which
        typically reflects the root / collision component only -- and so
        understates Blueprint composites with non-colliding visual meshes.
        For visual alignment (e.g. computing spawn offsets), prefer
        :meth:`get_obj_obb`, which aggregates every primitive component.

        Args:
            obj_id: Object ID, or ``None`` for every object in the scene.

        Returns:
            Raw JSON envelope ``{"status", "outputs": [...]}`` where each
            output carries ``aabb``, ``obb``, ``bounds``, ``bounds_tight``
            and pose / scale / color metadata.
        """
        if obj_id is None:
            res = self.client.request("lych obj get_aabb -all")
        else:
            res = self.client.request(f"lych obj get_aabb {obj_id}")
        return json.loads(res)

    def get_obj_obb(self, obj_id: str) -> tuple[np.ndarray, np.ndarray]:
        """Get the world-space oriented bounding box for an object.

        Backed by ``Actor->GetActorBounds(false, ...)``, which aggregates
        all registered primitive components (including non-colliding
        visual meshes). This is the right bbox flavor for visual
        alignment such as bottom-center spawn-offset computation.

        Args:
            obj_id: Object ID.

        Returns:
            Tuple ``(center, extent_rotation)`` of ``np.ndarray``: the
            first is shape ``(3,)`` in world cm; the second packs the
            half-sizes followed by the rotation as returned by the
            C++ handler.
        """
        res = self.client.request(f"lych obj get_obb {obj_id}")
        res = [float(x) for x in res.strip().split(" ")]
        return np.array(res[:3]), np.array(res[3:])

    def get_obj_loc(self, obj_id: str | list[str] = None) -> dict:
        """Get object world locations.

        Arguments:
            obj_id: A single object ID, a list of object IDs, or ``None``
                to query every object in the scene.

        Returns:
            The raw JSON from the C++ handler::

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
            mix. Locations are in Unreal world coordinates (centimeters,
            left-handed, Z-up).
        """
        if obj_id is None:
            res = self.client.request("lych obj get_loc -all")
        else:
            if isinstance(obj_id, str):
                ids = obj_id
            else:
                ids = " ".join(obj_id)
            res = self.client.request(f"lych obj get_loc {ids}")
        return json.loads(res)

    def get_obj_rot(self, obj_id: str | list[str] = None) -> dict:
        """Get object world rotations.

        Arguments:
            obj_id: A single object ID, a list of object IDs, or ``None``
                to query every object in the scene.

        Returns:
            The raw JSON from the C++ handler, using the same shape as
            :meth:`get_obj_loc` but with a ``"rotation": [pitch, yaw,
            roll]`` field (degrees) instead of ``"location"``::

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
        """
        if obj_id is None:
            res = self.client.request("lych obj get_rot -all")
        else:
            if isinstance(obj_id, str):
                ids = obj_id
            else:
                ids = " ".join(obj_id)
            res = self.client.request(f"lych obj get_rot {ids}")
        return json.loads(res)

    def update_obj(self, obj_id, loc: list | np.ndarray = None, rot: list | np.ndarray = None) -> None:
        """Update an existing actor's location and/or rotation in place.

        Args:
            obj_id: Object ID of an actor already in the scene.
            loc: New world-space ``[x, y, z]`` in cm. If ``None``, the
                current location is preserved.
            rot: New ``[pitch, yaw, roll]`` in degrees. If ``None``, the
                current rotation is preserved.

        Raises:
            ValueError: If both ``loc`` and ``rot`` are ``None``.
        """
        if loc is None and rot is None:
            raise ValueError("Either loc or rot must be provided.")
        params = ""
        if loc is not None:
            if isinstance(loc, np.ndarray):
                loc = loc.tolist()
            loc = ",".join(map(str, loc))
            params += f" -loc={loc}"
        if rot is not None:
            if isinstance(rot, np.ndarray):
                rot = rot.tolist()
            rot = ",".join(map(str, rot))
            params += f" -rot={rot}"
        self.client.request(f"lych obj update {obj_id}{params}")

    def get_obj_mask(
        self, cam_id: int, obj_id: str | list[str] = None
    ) -> tuple[list[str], np.ndarray]:
        """Get object mask(s) from a specific camera.

        Arguments:
            cam_id: Camera ID.
            obj_id: If specified, get the mask for this object. If a list of object IDs
                is provided, get the masks for these objects. If None, get the mask for
                all visible objects.

        Returns:
            A list of object masks.
        """
        res = self.client.request("lych object list")
        all_object_ids = res.strip().split(" ")

        object_mask = np.array(self.get_cam_seg(cam_id))

        regexp = re.compile(r"\(R=(.*),G=(.*),B=(.*),A=(.*)\)")

        vis_objects = []
        for obj_id in all_object_ids:
            color_str = self.client.request(f"vget /object/{obj_id}/color")
            match = regexp.match(color_str)
            if not match:
                raise ValueError(f"Invalid color string: {color_str}")
            r, g, b, _ = [int(match.group(i)) for i in range(1, 5)]

            mask = np.all(object_mask[:, :, :3] == [r, g, b], axis=-1)

            area = np.sum(mask)
            if area > 0:
                vis_objects.append((area, obj_id, mask))

        vis_objects.sort(reverse=True)
        vis_masks = np.stack([mask for _, _, mask in vis_objects], axis=0)
        return [obj_id for _, obj_id, _ in vis_objects], vis_masks

    def list_selected(self) -> dict:
        """Return the actors currently selected in the Unreal editor.

        Useful when authoring in the editor and you want to round-trip a
        selection into Python.

        Returns:
            Raw JSON envelope with selected object IDs under ``outputs``.
        """
        res = self.client.request("lych obj list_selected")
        return json.loads(res)

    def get_obj_annots(self, obj_id: str | list[str] = None) -> dict:
        """Get the full annotation record for one or more objects.

        This is the workhorse query for scene state -- it returns
        everything the C++ side knows about each requested actor.

        Args:
            obj_id: A single object ID, a list of object IDs, or ``None``
                to query every object in the scene.

        Returns:
            Raw JSON envelope ``{"status", "outputs": [...]}`` where each
            output entry contains ``object_id``, ``status``, ``guid``,
            ``aabb`` / ``obb`` / ``bounds`` / ``bounds_tight`` (each with
            ``center`` and ``extent``; OBB also has ``rotation``),
            ``location`` (cm), ``rotation`` (deg), ``scale``, and
            ``color`` (the 4-channel segmentation color used by
            :meth:`get_cam_seg`). Locations are in Unreal world
            coordinates (centimeters, left-handed, Z-up); rotations are
            ``[pitch, yaw, roll]`` in degrees.

        Raises:
            ValueError: If the C++ response is not parseable JSON.
        """
        if obj_id is None:
            obj_id_str = "-all"
        else:
            if isinstance(obj_id, str):
                obj_id = [obj_id]
            obj_id_str = " ".join(obj_id)
        res = self.client.request(f"lych obj get_annots {obj_id_str}")
        try:
            return json.loads(res)
        except Exception:
            raise ValueError(f"Failed to parse JSON: {res}")

    def add_obj(
        self, obj_id: str, obj_path: str, loc: list | np.ndarray, rot: list | np.ndarray,
        scale: float = 1.0, skip_if_colliding: bool = False, adjust_if_possible: bool = False,
        lock_rotation: bool = False,
    ) -> None:
        """Spawn a new actor in the running scene.

        Args:
            obj_id: ID to assign to the new actor (must be unique).
            obj_path: Unreal asset content path to spawn, e.g.
                ``/Game/HousePropsFurniture/Blueprints/BP_Toilet.BP_Toilet``.
            loc: Spawn location ``[x, y, z]`` in cm.
            rot: Spawn rotation ``[pitch, yaw, roll]`` in degrees.
            scale: Uniform scale factor. Default 1.0.
            skip_if_colliding: If True, abort the spawn when the actor
                would overlap an existing one. Mutually exclusive with
                ``adjust_if_possible``.
            adjust_if_possible: If True, nudge the spawn location to
                resolve collisions instead of aborting.
            lock_rotation: If True, freeze the actor's rotation against
                physics so it doesn't tip / spin under gravity.

        Returns:
            Raw JSON envelope describing the spawn outcome.

        Raises:
            AssertionError: If ``skip_if_colliding`` and
                ``adjust_if_possible`` are both True.
        """
        if isinstance(loc, np.ndarray):
            loc = loc.tolist()
        if isinstance(rot, np.ndarray):
            rot = rot.tolist()
        loc_str = " ".join(map(str, loc))
        rot_str = " ".join(map(str, rot))
        cmd = f"lych obj add {obj_id} {obj_path} {loc_str} {rot_str} {scale}"

        assert not (skip_if_colliding and adjust_if_possible), \
            "skip_if_colliding and adjust_if_possible cannot both be True."
        if skip_if_colliding:
            cmd += " -skipIfColliding"
        if adjust_if_possible:
            cmd += " -adjustIfPossible"
        if lock_rotation:
            cmd += " -lockRotation"

        res = self.client.request(cmd)
        return json.loads(res)

    def del_obj(self, obj_id: str) -> None:
        """Delete an actor from the running scene.

        Args:
            obj_id: Object ID of the actor to remove.
        """
        self.client.request(f"lych obj del {obj_id}")

    def get_mesh_extent(self, obj_id: str | list[str]) -> dict:
        """Get an actor's static-mesh extent (half-sizes from the asset).

        This reads from the underlying static-mesh asset rather than the
        spawned actor bounds, so it is independent of pose and ignores
        any blueprint-time scaling. Useful for sizing-driven sampling
        decisions before placement.

        Args:
            obj_id: Object ID, or list of object IDs.

        Returns:
            Raw JSON envelope ``{"status", "outputs": [...]}`` where each
            output carries the asset-space half-extents.

        Raises:
            ValueError: If the C++ response is not parseable JSON.
        """
        obj_id_str = obj_id if isinstance(obj_id, str) else " ".join(obj_id)
        res = self.client.request(f"lych obj get_mesh_extent {obj_id_str}")
        try:
            return json.loads(res)
        except Exception:
            raise ValueError(f"Failed to parse JSON: {res}")

    def export_meshes(
        self,
        root_path: str | None = None,
        output_dir: str | None = None,
        max_count: int | None = None,
        recursive: bool = True,
        glb_only: bool = False,
        keep_extras: bool = False,
    ):
        """Export static meshes under the given content path to glTF and glb files.

        Args:
            root_path: Content path to scan, e.g. /Game/AIUE5_vol8_01/Mesh.
            output_dir: Destination directory for exported files.
            max_count: Limit number of meshes to export (useful for testing).
            recursive: Whether to search subfolders.
            glb_only: If True, only export .glb and skip .gltf.
            keep_extras: If False, will remove ancillary files (bin/png) after export when gltf is produced.
        """
        cmd = "lych obj export_meshes"
        if root_path:
            cmd += f" {root_path}"
        if output_dir:
            cmd += f" -out={output_dir}"
        if max_count is not None:
            cmd += f" -max={max_count}"
        if not recursive:
            cmd += " -norecursive"
        if glb_only:
            cmd += " -glb_only"
        if keep_extras:
            cmd += " -keep_extras"
        res = self.client.request(cmd)
        try:
            return json.loads(res)
        except Exception:
            return res

    def adjust_light(
        self, obj_id: str, intensity: float = None,
        rot: list[float] = None, color: list[int] = None, temp: int = None
    ) -> bool:
        params = ""
        if intensity is not None:
            params += f" -intensity={intensity}"
        if rot is not None:
            rot_str = ",".join(map(str, rot))
            params += f" -rot={rot_str}"
        if color is not None:
            color_str = ",".join(map(str, color))
            params += f" -color={color_str}"
        if temp is not None:
            params += f" -temp={temp}"
        res = self.client.request(f"lych obj adjust_light {obj_id}{params}")
        return json.loads(res)["status"] == "ok"
