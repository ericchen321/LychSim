from ..api import Client
from .camera_mixin import CameraCommandsMixin
from .data_mixin import DataCommandsMixin
from .object_mixin import ObjectCommandsMixin


class LychSim(CameraCommandsMixin, DataCommandsMixin, ObjectCommandsMixin):
    """High-level Python wrapper for a running LychSim / Unreal Engine instance.

    Composes :class:`CameraCommandsMixin`, :class:`ObjectCommandsMixin`, and
    :class:`DataCommandsMixin`, so every camera / object / simulation
    command is available as a method on this single class.

    Constructing an instance opens a socket connection to the UnrealCV +
    LychSim plugin running inside UE; ``close()`` tears it down. The usual
    pattern is::

        sim = LychSim(server_name="localhost", port=9000, width=1920, height=1080)
        try:
            rgb = sim.get_cam_lit(cam_id=0)
        finally:
            sim.close()
    """

    def __init__(
        self,
        server_name: str = "localhost",
        port: int = 9000,
        width: int = 640,
        height: int = 480,
    ) -> None:
        """Connect to a running LychSim instance and resize camera 0.

        Args:
            server_name: Host running the UE / UnrealCV server. Default
                ``"localhost"``.
            port: UnrealCV TCP port. Default ``9000``.
            width: Capture width in pixels. Default ``640``. Note this
                resizes camera 0's film size on connect (see
                :meth:`post_init`).
            height: Capture height in pixels. Default ``480``.
        """
        self.server_name = server_name
        self.port = port
        self.width = width
        self.height = height

        self.client = Client((server_name, port))
        self.client.connect()

        self.post_init()

    def post_init(self) -> None:
        """Run after :meth:`__init__` to prime per-instance state.

        Sets up the warmup-camera bookkeeping and resizes camera 0 to
        ``width`` x ``height`` via ``lych cam set_film_size 0 ...``. If you
        are capturing from a different camera and care about camera 0's
        existing resolution, leave the constructor's defaults at the
        running instance's actual size.
        """
        self.warmup_cameras = set()
        self.client.request(f"lych cam set_film_size 0 {self.width} {self.height}")

    def print_status(self) -> str:
        """Print the C++ status string (server / client info, configuration)."""
        print(self.client.request("lych status"))

    def get_status(self) -> str:
        """Return the C++ status string (server / client info, configuration)."""
        return self.client.request("lych status")

    def close(self) -> None:
        """Disconnect from the LychSim server and stop the receive thread."""
        self.client.disconnect()
