from typing import Any, Dict

import numpy as np

from lychsim.utils import FACES

__all__ = ['AABB', 'OBB']


def get_corners(min_pt, max_pt):
    """Return the eight corners of a 3D box defined by min / max points.

    Args:
        min_pt: ``(x_min, y_min, z_min)`` -- the box's minimum corner.
        max_pt: ``(x_max, y_max, z_max)`` -- the box's maximum corner.

    Returns:
        ``np.ndarray`` of shape ``(8, 3)`` listing the corners. The first
        four are the bottom face (``z = z_min``), going counter-clockwise
        from ``(x_min, y_min, z_min)``; the last four are the top face,
        in matching order.
    """
    min_x, min_y, min_z = min_pt
    max_x, max_y, max_z = max_pt
    points = np.array([
        [min_x, min_y, min_z],
        [max_x, min_y, min_z],
        [max_x, max_y, min_z],
        [min_x, max_y, min_z],
        [min_x, min_y, max_z],
        [max_x, min_y, max_z],
        [max_x, max_y, max_z],
        [min_x, max_y, max_z],
    ])
    return points


class AABB:
    """Axis-aligned bounding box represented by a center, half-extents, and a translation.

    The box is defined in a local frame by ``center +/- extent``, then
    shifted into world space by ``translation``. Use :attr:`AABB.corners` to
    materialize the eight world-space corner points.
    """

    def __init__(
        self, center: np.ndarray = None, extent: np.ndarray = None,
        translation: np.ndarray = None
    ):
        """Construct an AABB.

        Args:
            center: ``(3,)`` array -- box center in the local frame.
            extent: ``(3,)`` array of half-sizes along each local axis.
            translation: ``(3,)`` array -- offset to apply to
                :attr:`AABB.corners` before returning.
        """
        self.center = center
        self.extent = extent
        self.translation = translation

    def __repr__(self):
        return (
            f"AABB(center={tuple(self.center.tolist())}, "
            f"extent={tuple(self.extent.tolist())}), "
            f'translation={tuple(self.translation.tolist())})')

    @property
    def corners(self):
        """Returns the corners of the AABB.
        """
        corners = get_corners(
            self.center - self.extent,
            self.center + self.extent)
        return corners + self.translation

    def to_dict(self):
        """Returns a dictionary representation of the AABB.
        """
        return dict(
            center=self.center.tolist(),
            extent=self.extent.tolist(),
            translation=self.translation.tolist())

    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]):
        return cls(
            center=np.array(data_dict['center']),
            extent=np.array(data_dict['extent']),
            translation=np.array(data_dict['translation']))

    def __eq__(self, other):
        if not isinstance(other, AABB):
            return False
        return (np.array_equal(self.center, other.center) and
                np.array_equal(self.extent, other.extent) and
                np.array_equal(self.translation, other.translation))


class OBB:
    """Oriented bounding box: an :class:`AABB` plus a 3x3 rotation matrix.

    The box is defined in a local frame by ``center +/- extent``,
    rotated by ``rotation``, then translated into world space by
    ``translation``. :attr:`OBB.corners` returns the eight world-space
    corners with the rotation applied.
    """

    def __init__(
        self, center: np.ndarray = None, extent: np.ndarray = None,
        rotation: np.ndarray = None, translation: np.ndarray = None
    ):
        """Construct an OBB.

        Args:
            center: ``(3,)`` array -- box center in the local frame.
            extent: ``(3,)`` array of half-sizes along each local axis.
            rotation: ``(3, 3)`` rotation matrix that orients the local
                frame in world space.
            translation: ``(3,)`` array -- world-space offset applied
                after the rotation.
        """
        self.center = center
        self.extent = extent
        self.rotation = rotation
        self.translation = translation

    def __repr__(self):
        return (
            f'OBB(center={tuple(self.center.tolist())}, '
            f'extent={tuple(self.extent.tolist())}, '
            f'rotation={self.rotation.tolist()}, '
            f'translation={tuple(self.translation.tolist())})')

    @property
    def corners(self):
        """Returns the corners of the OBB.
        """
        corners = get_corners(
            self.center - self.extent,
            self.center + self.extent)
        return (self.rotation @ corners.T).T + self.translation

    def to_dict(self):
        """Returns a dictionary representation of the AABB.
        """
        return dict(
            center=self.center.tolist(),
            extent=self.extent.tolist(),
            rotation=self.rotation.tolist(),
            translation=self.translation.tolist())

    @classmethod
    def from_dict(cls, data_dict: Dict[str, Any]):
        return cls(
            center=np.array(data_dict['center']),
            extent=np.array(data_dict['extent']),
            rotation=np.array(data_dict['rotation']),
            translation=np.array(data_dict['translation']))

    def __eq__(self, other):
        if not isinstance(other, OBB):
            return False
        return (np.array_equal(self.center, other.center) and
                np.array_equal(self.extent, other.extent) and
                np.array_equal(self.rotation, other.rotation) and
                np.array_equal(self.translation, other.translation))
