import numpy as np
import seaborn as sns

__all__ = ['COLORMAPS_INT', 'COLORMAPS_FLOAT', 'COLORMAPS_HEX']

COLORMAPS_INT = {}

# Seaborn Set2 categorical colors
COLORMAPS_INT['sns_set2'] = [
    [round(v * 255) for v in c]
    for c in sns.color_palette('Set2')]

COLORMAPS_FLOAT = {
    k: [[x / 255.0 for x in c] for c in v]
    for k, v in COLORMAPS_INT.items()}

COLORMAPS_HEX = {
    k: ['#{:02x}{:02x}{:02x}'.format(*c) for c in v]
    for k, v in COLORMAPS_INT.items()}
