from .bbox import OBB

__all__ = ['Object']


class Object:
    """A scene-graph leaf node: a named, uniquely-identified object with an oriented bounding box.

    These are the leaves under :class:`~lychsim.core.SemanticRegion`. The
    ``obb`` field carries the world-space pose and extent.
    """

    def __init__(
        self, name: str = None, uid: str = None, obb: OBB = None
    ):
        """Construct an :class:`Object`.

        Args:
            name: Human-readable name (e.g. ``"chair_3"``).
            uid: Stable unique identifier across serialization round-trips.
            obb: World-space :class:`~lychsim.core.OBB` for this object.
        """
        self.name = name
        self.uid = uid
        self.obb = obb

    def to_dict(self):
        """Returns a dictionary representation of the Object.
        """
        return dict(
            name=self.name,
            uid=self.uid,
            obb=self.obb.to_dict() if self.obb is not None else None)

    @classmethod
    def from_dict(cls, data_dict: dict):
        return cls(
            name=data_dict['name'], uid=data_dict['uid'],
            obb=OBB.from_dict(data_dict['obb']) if data_dict['obb'] else None)

    def __eq__(self, other):
        if not isinstance(other, Object):
            return False
        return (self.name == other.name and self.uid == other.uid and
                self.obb == other.obb)
