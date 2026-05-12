"""``lychsim`` CLI entry point.

Currently only supports ``--version`` / ``-v``. Future subcommands
(``run``, ``list``, ``stop``, ...) live next to this file under
``commands/`` and are dispatched from here. See ``TODO_toolset.md``.
"""

from __future__ import annotations

import argparse
import platform
import sys
from importlib.metadata import PackageNotFoundError, version as _pkg_version


COPYRIGHT_YEARS = "2025-2026"


def _get_version() -> str:
    try:
        return _pkg_version("lychsim")
    except PackageNotFoundError:
        return "unknown (lychsim is not installed; try `pip install -e .`)"


def _version_banner() -> str:
    py_ver = platform.python_version()
    plat = f"{platform.system().lower()}-{platform.machine().lower()}"
    release = _get_version()
    return (
        "lychsim: LychSim simulation system\n"
        f"Copyright (c) {COPYRIGHT_YEARS} LychSim Team\n"
        f"Built on Python {py_ver} ({plat})\n"
        f"LychSim simulation tools, release v{release}"
    )


class _PrintBannerAction(argparse.Action):
    """Print the version banner verbatim (argparse's built-in version action
    re-wraps the text, which mangles a multi-line banner)."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, **kwargs):
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            nargs=0,
            help="show the lychsim version banner and exit",
        )

    def __call__(self, parser, namespace, values, option_string=None):
        print(_version_banner())
        parser.exit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lychsim",
        description="LychSim CLI -- launch and manage LychSim Unreal Engine instances.",
    )
    parser.add_argument("-v", "--version", action=_PrintBannerAction)

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # Order is workflow-driven (not registration-driven):
    # lifecycle (run / ps / logs / stop) -> registries (env / engine) -> doctor.

    from .commands import run as cmd_run
    p_run = subparsers.add_parser("run", help=cmd_run.HELP)
    cmd_run.add_arguments(p_run)
    p_run.set_defaults(func=cmd_run.run)

    from .commands import ps as cmd_ps
    p_ps = subparsers.add_parser("ps", help=cmd_ps.HELP)
    cmd_ps.add_arguments(p_ps)
    p_ps.set_defaults(func=cmd_ps.run)

    from .commands import logs as cmd_logs
    p_logs = subparsers.add_parser("logs", help=cmd_logs.HELP)
    cmd_logs.add_arguments(p_logs)
    p_logs.set_defaults(func=cmd_logs.run)

    from .commands import capture as cmd_capture
    p_capture = subparsers.add_parser("capture", help=cmd_capture.HELP)
    cmd_capture.add_arguments(p_capture)
    p_capture.set_defaults(func=cmd_capture.run)

    from .commands import stop as cmd_stop
    p_stop = subparsers.add_parser("stop", help=cmd_stop.HELP)
    cmd_stop.add_arguments(p_stop)
    p_stop.set_defaults(func=cmd_stop.run)

    from .commands import env as cmd_env
    p_env = subparsers.add_parser("env", help=cmd_env.HELP)
    cmd_env.add_arguments(p_env)
    # cmd_env.add_arguments installs per-subcommand `func` defaults plus a
    # fallback for "no subcommand given".

    from .commands import engine as cmd_engine
    p_engine = subparsers.add_parser("engine", help=cmd_engine.HELP)
    cmd_engine.add_arguments(p_engine)
    # cmd_engine.add_arguments installs its own per-subcommand `func` defaults
    # plus a fallback for "no subcommand given".

    from .commands import doctor as cmd_doctor
    p_doctor = subparsers.add_parser("doctor", help=cmd_doctor.HELP)
    cmd_doctor.add_arguments(p_doctor)
    p_doctor.set_defaults(func=cmd_doctor.run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 0
    return func(args)


if __name__ == "__main__":
    sys.exit(main())
