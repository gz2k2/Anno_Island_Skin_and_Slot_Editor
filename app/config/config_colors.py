"""Bright colors for RD3D/TMC Type categories in the dark-mode GUI.

Colors are grouped into visually distinct hue families.  The application uses
one family per category during the first assignment cycle and only starts using
additional shades from an already-used family after every family has been used.
"""

TYPE_CATEGORY_COLOR_FAMILIES = {
    "red": ("#FF0000", "#FF4D4D", "#FF6B6B", "#FF7675"),
    "orange": ("#FF8A3D", "#FF9F43", "#FFB347"),
    "yellow": ("#FFFF00", "#FFD166", "#FECA57"),
    "green": ("#00FF00", "#00FFAA", "#26DE81", "#55EFC4"),
    "cyan": ("#00E5E5", "#22D3EE", "#48DBFB"),
    "blue": ("#45AAF2", "#54A0FF", "#74B9FF"),
    "purple": ("#9D34FF", "#D980FA"),
    "pink": ("#FF4FA3", "#FD79A8", "#F06292"),
}

# Backward-compatible flat palette for existing imports/code.
TYPE_CATEGORY_COLORS = tuple(
    color
    for family in TYPE_CATEGORY_COLOR_FAMILIES.values()
    for color in family
)

DEFAULT_TYPE_COLOR = "#B2BEC3"
