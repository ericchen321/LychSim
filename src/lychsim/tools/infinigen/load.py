from collections import defaultdict
from dataclasses import dataclass
import json
import logging
import os
from typing import Any, Dict

from einops import pack, rearrange
import numpy as np
from PIL import Image
from shapely import Polygon

from lychsim.core import OBB, Object
from lychsim.core import SemanticScene, SemanticLevel, SemanticRegion
from lychsim.utils import ModelOutput

__all__ = ['load_infinigen_frame', 'InfinigenFrameOutput']


@dataclass
class InfinigenFrameOutput(ModelOutput):
    scene: SemanticScene = None
    camera_index: int = None
    frame_index: int = None
    camera_pose: np.ndarray = None
    K: np.ndarray = None
    image: np.ndarray = None
    depth: np.ndarray = None
    visibility: Dict[str, bool] = None


def recover(d):
    return d['vals'][d['indices']].reshape(d['shape'])


def room_level(name: str) -> int:
    return int(name.split('/')[0].split('_')[1])


def compute_outer_loop(edges):
    edge_count = defaultdict(int)
    edge_map = defaultdict(list)

    for e in edges:
        a, b = sorted(e)
        edge_count[(a, b)] += 1
        edge_map[a].append(b)
        edge_map[b].append(a)

    boundary_edges = [e for e in edges if edge_count[tuple(sorted(e))] == 1]

    if not boundary_edges:
        return []

    loop = []
    used = set()
    v_start = boundary_edges[0][0]
    v = v_start
    prev = None

    while True:
        loop.append(v)
        used.add(v)
        neighbors = [n for n in edge_map[v] if n != prev]
        found = False
        for n in neighbors:
            if tuple(sorted((v, n))) in map(lambda x: tuple(sorted(x)), boundary_edges):
                prev = v
                v = n
                found = True
                break
        if not found or v == v_start:
            break

    return loop


def load_floor(mesh_path: str, mesh: Dict[str, Any]):
    data = np.load(os.path.join(mesh_path, mesh['filename']))
    mesh_id = mesh['mesh_id']
    mesh_indices = data[f'{mesh_id}_indices']
    mesh_vertices = data[f'{mesh_id}_vertices']
    mesh_loop_totals = data[f'{mesh_id}_loop_totals']

    mesh_vertices = mesh_vertices[:, :2]

    offset, edges = 0, []
    for loop_size in mesh_loop_totals:
        indices = mesh_indices[offset:offset + loop_size]
        for i in range(len(indices)):
            if i == len(indices) - 1:
                edges.append([indices[i], indices[0]])
            else:
                edges.append([indices[i], indices[i+1]])
        offset += loop_size

    outer_loop = compute_outer_loop(edges)
    outer_loop = Polygon(mesh_vertices[outer_loop])

    return outer_loop


def create_scene(
    scene_json: str, objects: list[Object], room_meshes: list[Polygon]
) -> SemanticScene:
    all_objs = json.load(open(scene_json, 'r'))['objs']
    semantic_rooms = [
        k for k, obj in all_objs.items() if 'Semantics(room)' in obj['tags']]
    semantic_objects = [
        k for k, obj in all_objs.items() if 'Semantics(object)' in obj['tags']]

    room_child_mapping = defaultdict(list)
    for obj_name in semantic_objects:
        target_rooms = list(set([
            r['target_name'] for r in all_objs[obj_name]['relations']
            if r['relation']['relation_type'] == 'StableAgainst']))
        assert len(target_rooms) == 1, (
            f'Target rooms of object {obj_name} is not equal to 1: '
            f'{", ".join(target_rooms)}.')
        room_child_mapping[target_rooms[0]].append(
            all_objs[obj_name]['obj'])

    levels = {}
    for room_name in semantic_rooms:
        region = SemanticRegion(
            name=room_name,
            polygon=room_meshes[room_name+'.floor'],
            obb=objects[room_name+'.floor'].obb)
        for obj_name in room_child_mapping[room_name]:
            region.objects.append(objects[obj_name])
        level_name = f'level_{room_level(room_name)}'
        if level_name not in levels:
            levels[level_name] = SemanticLevel(name=level_name)
        levels[level_name].regions.append(region)

    return SemanticScene(
        name='default_scene',
        levels=[levels[k] for k in sorted(levels.keys())])


def load_infinigen_frame(
    scene_folder: str, camera_index: int = None, frame_index: int = None,
    loads: list[str] = ['scene', 'camera', 'image', 'depth', 'visibility']
) -> InfinigenFrameOutput:
    if not os.path.exists(scene_folder):
        raise FileNotFoundError(
            f"Infinigen scene folder '{scene_folder}' does not exist.")

    if camera_index is None:
        cameras = os.listdir(os.path.join(scene_folder, 'frames', 'camview'))
        camera_index = int(sorted(cameras)[0].split('_')[1])

    if frame_index is None:
        frames = os.listdir(os.path.join(
            scene_folder, 'frames', 'camview', f'camera_{camera_index}'))
        frame_index = int(sorted(frames)[0].split('_')[-2])

    logging.debug(
        f'Loading Infinigen scene from {scene_folder}, '
        f'camera {camera_index}, frame {frame_index}...')

    scene = None
    if 'scene' in loads:
        # 1. Load objects
        objects_path = os.path.join(
            scene_folder, 'frames', 'Objects', f'camera_{camera_index}',
            f'Objects_0_0_{frame_index:04d}_{camera_index}.json')
        if not os.path.isfile(objects_path):
            raise FileNotFoundError(
                f'Frame objects file {objects_path} not found.')
        with open(objects_path, 'r') as fp:
            raw_objects = json.load(fp)

        objects = {}
        for ro in raw_objects:
            if ro['min'] is None or ro['max'] is None:
                logging.debug(
                    f'Object {ro["name"]} ({ro["object_index"]}) '
                    'has no bounding box.')
                obb = None
            else:
                min_point = np.array(ro['min'])
                max_point = np.array(ro['max'])
                translation = np.array([
                    ro['model_matrices'][0][0][3],
                    ro['model_matrices'][0][1][3],
                    ro['model_matrices'][0][2][3]])
                obb = OBB(
                    center=(min_point + max_point) / 2,
                    extent=(max_point - min_point) / 2,
                    rotation=np.array(ro['model_matrices'][0])[:3, :3],
                    translation=translation)
            objects[ro['name']] = Object(
                name=ro['name'],
                uid=(
                    f'{ro["object_index"]}_'
                    f'{ro["instance_ids"][0][0]}_'
                    f'{ro["instance_ids"][0][1]}_'
                    f'{ro["instance_ids"][0][2]}'
                ),
                obb=obb)

        # 2. Load room-level data
        mesh_path = os.path.join(
            scene_folder, f'savemesh_0_0_{frame_index:04d}_{camera_index}',
            f'frame_{frame_index:04d}', 'mesh')
        with open(os.path.join(mesh_path, 'saved_mesh.json'), 'r') as fp:
            mesh_metadata = json.load(fp)
        room_meshes = {}
        for mesh in mesh_metadata:
            if 'floor' in mesh['object_name']:
                room_meshes[mesh['object_name']] = load_floor(mesh_path, mesh)

        # 3. Create scene from scene-level data
        solve_state_path = os.path.join(
            scene_folder, 'coarse', 'solve_state.json')
        scene = create_scene(solve_state_path, objects, room_meshes)

    camera_pose, K = None, None
    if 'camera' in loads:
        camview = np.load(os.path.join(
            scene_folder, 'frames', 'camview', f'camera_{camera_index}',
            f'camview_0_0_{frame_index:04d}_{camera_index}.npz'))
        camera_pose, K = camview['T'], camview['K']

    image = None
    if 'image' in loads:
        image_path = os.path.join(
            scene_folder, 'frames', 'Image', f'camera_{camera_index}',
            f'Image_0_0_{frame_index:04d}_{camera_index}.png')
        if not os.path.isfile(image_path):
            raise FileNotFoundError(
                f'Frame image file {image_path} not found.')
        image = np.array(Image.open(image_path))

    depth = None
    if 'depth' in loads:
        depth_path = os.path.join(
            scene_folder, 'frames', 'Depth', f'camera_{camera_index}',
            f'Depth_0_0_{frame_index:04d}_{camera_index}.npy')
        if not os.path.isfile(depth_path):
            raise FileNotFoundError(
                f'Frame depth file {depth_path} not found.')
        depth = np.load(depth_path)

    visibility = None
    if 'visibility' in loads:
        assert 'scene' in loads, (
            "Visibility can only be loaded if 'objects' is also requested.")
        object_segmentation_path = os.path.join(
            scene_folder, 'frames', 'ObjectSegmentation',
            f'camera_{camera_index}',
            f'ObjectSegmentation_0_0_{frame_index:04d}_{camera_index}.npz')
        instance_segmentation_path = os.path.join(
            scene_folder, 'frames', 'InstanceSegmentation',
            f'camera_{camera_index}',
            f'InstanceSegmentation_0_0_{frame_index:04d}_{camera_index}.npz')
        if not os.path.isfile(object_segmentation_path):
            raise FileNotFoundError(
                f'Frame object segmentation file {object_segmentation_path} '
                'not found.')
        if not os.path.isfile(instance_segmentation_path):
            raise FileNotFoundError(
                'Frame instance segmentation file '
                f'{instance_segmentation_path} not found.')
        object_segmentation_mask = recover(np.load(object_segmentation_path))
        instance_segmentation_mask = recover(
            np.load(instance_segmentation_path))
        combined_mask, _ = pack(
            [object_segmentation_mask, instance_segmentation_mask], 'h w *')
        combined_mask = rearrange(combined_mask, 'h w d -> (h w) d')
        visible_instances = np.unique(combined_mask, axis=0)
        visible_instances = {
            f'{row[0]}_{row[1]}_{row[2]}_{row[3]}'
            for row in visible_instances}
        visibility = {
            obj.uid: obj.uid in visible_instances
            for obj in objects.values()}

    return InfinigenFrameOutput(
        scene=scene,
        camera_index=camera_index,
        frame_index=frame_index,
        camera_pose=camera_pose,
        K=K,
        image=image,
        depth=depth,
        visibility=visibility)
