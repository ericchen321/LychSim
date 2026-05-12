import argparse
import os

import numpy as np

from lychsim.core import SemanticScene
from lychsim.tools.infinigen import load_infinigen_frame


def parse_args():
    parser = argparse.ArgumentParser(
        description='Load Infinigen scene to LychSim format and save to file.')
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

    save_path = os.path.join(args.output_path, 'scene.npz')

    # save scene
    np.savez(save_path, data=infinigen_frame.scene.to_dict())

    # load scene
    scene_loaded = SemanticScene.from_npz(save_path)

    assert infinigen_frame.scene == scene_loaded, \
        "Loaded scene does not match the original scene."


if __name__ == '__main__':
    main()
