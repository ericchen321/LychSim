import argparse
import os

import cv2
import numpy as np
from PIL import Image

from lychsim.tools.infinigen import load_infinigen_frame
from lychsim.utils import rgbd2rgb, FACES


def parse_args():
    parser = argparse.ArgumentParser(description="Visualize Infinigen BBox3D")
    parser.add_argument('--scene_path', type=str,
                        default='/path/to/infinigen/scene')
    parser.add_argument('--output_folder', type=str, default='lychsim')
    return parser.parse_args()


def plot_obb(image, obj, camera_pose_inv, K):
    corners = obj.obb.corners
    corners = (
        camera_pose_inv[:3, :3] @ corners.T
        + camera_pose_inv[:3, 3:]
    ).T
    corners = (K @ corners.T).T

    if corners[:, 2].min() < 0:
        return

    corners = (corners[:, :2] / corners[:, 2:3]).astype(int)

    for face in FACES:
        normal = np.cross(
            corners[face[1]] - corners[face[0]],
            corners[face[2]] - corners[face[0]])
        if normal >= 0:
            continue
        for i in range(4):
            start = corners[face[i]]
            end = corners[face[(i + 1) % 4]]
            cv2.line(image, tuple(start), tuple(end), (255, 255, 0), 2)


def main():
    args = parse_args()
    args.output_path = os.path.join(args.scene_path, args.output_folder)

    infinigen_frame = load_infinigen_frame(
        args.scene_path, camera_index=0)
    print(len(infinigen_frame.scene.get_all_objects()), "objects loaded")
    print(sum(infinigen_frame.visibility.values()), "objects visible")

    orig_image = rgbd2rgb(infinigen_frame.image)
    plot_image = orig_image.copy()

    camera_pose_inv = np.linalg.inv(infinigen_frame.camera_pose)
    K = infinigen_frame.K
    for obj in infinigen_frame.scene.get_all_objects():
        if not infinigen_frame.visibility[obj.uid]:
            continue
        if obj.obb is None:
            continue
        plot_obb(plot_image, obj, camera_pose_inv, K)

    os.makedirs(args.output_path, exist_ok=True)
    Image.fromarray(np.concatenate([
        plot_image
    ], axis=1)).save(os.path.join(
        args.output_path,
        f'bbox3d_cam{infinigen_frame.camera_index}_'
        f'frame{infinigen_frame.frame_index}.png'))


if __name__ == '__main__':
    main()
