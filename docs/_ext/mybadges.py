from sphinx.application import Sphinx
from sphinx_design.badges_buttons import BadgeRole

BADGE_COLORS = [
    "red",
    "pink",
    "purple",
    "deeppurple",
    "indigo",
    "blue",
    "lightblue",
    "cyan",
    "teal",
    "green",
    "lightgreen",
    "lime",
    "yellow",
    "amber",
    "orange",
    "deeporange",
]


def add_badges(app: Sphinx) -> None:
    for color in BADGE_COLORS:
        app.add_role(f"bdg-{color}", BadgeRole(color))
    for color in BADGE_COLORS:
        app.add_role(f"bdg-{color}-line", BadgeRole(color, outline=True))


def add_css(app: Sphinx) -> None:
    app.add_css_file("css/mybadges.css")


def setup(app: Sphinx) -> None:
    add_badges(app)
    add_css(app)
