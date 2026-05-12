import argparse
import os

from matplotlib.patches import Polygon
import matplotlib.pyplot as plt
import numpy as np

from lychsim.utils import COLORMAPS_HEX
from lychsim.tools.infinigen import load_infinigen_frame


def parse_args():
    parser = argparse.ArgumentParser(
        description='Visualize Infinigen SemanticRegion.')
    parser.add_argument('--scene_path', type=str,
                        default='/path/to/infinigen/scene')
    parser.add_argument('--output_folder', type=str, default='lychsim')
    return parser.parse_args()


def main():
    args = parse_args()
    args.output_path = os.path.join(args.scene_path, args.output_folder)
    os.makedirs(args.output_path, exist_ok=True)

    infinigen_frame = load_infinigen_frame(
        args.scene_path, camera_index=0)
    print(len(infinigen_frame.scene.get_all_objects()), "objects loaded")
    print(sum(infinigen_frame.visibility.values()), "objects visible")

    regions = [
        region for region in infinigen_frame.scene.get_all_regions()
        if len(region.objects) > 0]

    for region in regions:
        print(f'Visualizing {region.name}...')

        fig, ax = plt.subplots(figsize=(8, 8))

        # Draw room floor
        floor_coords = np.array(region.polygon.exterior.coords[:])
        floor_coords = np.concatenate([
            floor_coords, np.zeros((floor_coords.shape[0], 1))], axis=1)
        floor_coords = (
            region.obb.rotation @ floor_coords.T
        ).T + region.obb.translation
        ax.add_patch(Polygon(
            floor_coords[:, :2], facecolor='#AED6F1',
            edgecolor='black', alpha=0.5, linewidth=2))

        xmin, xmax = floor_coords[:, 0].min()-0.5, floor_coords[:, 0].max()
        ymin, ymax = floor_coords[:, 1].min(), floor_coords[:, 1].max()
        xmin, xmax = xmin - 0.05 * (xmax - xmin), xmax + 0.05 * (xmax - xmin)
        ymin, ymax = ymin - 0.05 * (ymax - ymin), ymax + 0.05 * (ymax - ymin)

        plot_objects = []
        for obj in region.objects:
            corners = obj.obb.corners[:4]
            plot_objects.append((
                obj.name.split('Factory')[0],
                corners[:, :2].tolist(),
                np.mean(corners[:, :2], axis=0),
                float(corners[0, 2])))
        plot_objects.sort(key=lambda x: x[3])

        object_colors = COLORMAPS_HEX['sns_set2']
        for idx, obj in enumerate(plot_objects):
            ax.add_patch(Polygon(
                obj[1], facecolor=object_colors[idx % len(object_colors)]))
        for idx, obj in enumerate(plot_objects):
            ax.add_patch(Polygon(
                obj[1], facecolor='none', edgecolor='black'))
        for idx, obj in enumerate(plot_objects):
            x, y = obj[2]
            ax.text(
                x, y, obj[0], ha='center', va='center',
                fontsize=10, weight='bold')

        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect('equal')
        plt.tight_layout()

        save_path = os.path.join(
            args.output_path, f'region_{region.name.replace("/", "_")}.png')
        plt.savefig(save_path, dpi=200)


if __name__ == '__main__':
    main()
