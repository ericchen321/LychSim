import json

import numpy as np


class DataCommandsMixin:
    """Mixin for data-related commands."""

    def draw_debug_line(self, object_ids: list[str], color='green') -> None:
        """Draw a debug line connecting the center of a list of objects.

        Arguments:
            object_ids: List of object IDs.
        """
        res = self.client.request(f'lych data debug_line {" ".join(object_ids)} -color={color}')
        return json.loads(res)

    def draw_debug_line_pts(self, points: np.ndarray | list[list[float]], color='green', thickness=2.0) -> None:
        """Draw a debug line connecting a list of points.

        Arguments:
            points: List of points, each point is a list of 3 floats.
        """
        if isinstance(points, np.ndarray):
            points = points.tolist()

        for pt in points:
            assert len(pt) == 3, f"Each point must be a list of 3 floats, got {pt}"

        pts_str = " ".join([" ".join(map(str, pt)) for pt in points])
        res = self.client.request(f"lych data debug_line_pts {pts_str} -color={color} -thickness={thickness}")
        return json.loads(res)

    def clear_debug_lines(self) -> None:
        """Clear all debug lines."""
        res = self.client.request("lych data clear_debug_lines")
        return json.loads(res)

    def pause(self) -> dict:
        """Pause the simulation -- freezes physics, animations, and actor ticks.

        Calls ``lych data pause``. Useful for taking deterministic snapshots
        before reading camera/object state. Pair with :meth:`resume`.
        """
        return json.loads(self.client.request("lych data pause"))

    def resume(self) -> dict:
        """Resume a previously paused simulation. Calls ``lych data unpause``."""
        return json.loads(self.client.request("lych data unpause"))
