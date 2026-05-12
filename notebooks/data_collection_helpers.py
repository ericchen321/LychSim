import copy
import json
import os
from typing import Any

import cv2
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

from lychsim.api import LychSim
from lychsim.utils.camera_projection_utils import project_3d_to_2d, get_bbox3d


class EasyDict(dict):
    """Convenience class that behaves like a dict but allows access with the attribute syntax."""

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        self[name] = value

    def __delattr__(self, name: str) -> None:
        del self[name]


def init_sampling_params(state):
    # list of table and floor objects
    # will be provided by Xingrui and Siyi
    state.floor_objects = [
        "/Game/ManagerOffice/Meshes/Props/SM_AmchairTreadle.SM_AmchairTreadle",
        "/Game/ManagerOffice/Meshes/Props/SM_ArmchairManager.SM_ArmchairManager",
        "/Game/ManagerOffice/Meshes/Props/SM_ColumnTable.SM_ColumnTable",
        "/Game/ManagerOffice/Meshes/Props/SM_Decorative17.SM_Decorative17",
        "/Game/ManagerOffice/Meshes/Props/SM_Komod.SM_Komod",
        "/Game/ManagerOffice/Meshes/Props/SM_KomodB.SM_KomodB",
        "/Game/ManagerOffice/Meshes/Props/SM_Plant2.SM_Plant2",
        "/Game/ManagerOffice/Meshes/Props/SM_Plant1.SM_Plant1",
        "/Game/ManagerOffice/Meshes/Props/SM_TeaTable.SM_TeaTable",
    ]
    state.table_objects = [
        "/Game/ManagerOffice/Meshes/Props/SM_Ashtray.SM_Ashtray",
        "/Game/ManagerOffice/Meshes/Props/SM_Award3.SM_Award3",
        "/Game/ManagerOffice/Meshes/Props/SM_Award9.SM_Award9",
        "/Game/ManagerOffice/Meshes/Props/SM_Book2.SM_Book2",
        "/Game/ManagerOffice/Meshes/Props/SM_CalendarDesk.SM_CalendarDesk",
        "/Game/ManagerOffice/Meshes/Props/SM_Decorative10.SM_Decorative10",
        "/Game/ManagerOffice/Meshes/Props/SM_Decorative37.SM_Decorative37",
        "/Game/ManagerOffice/Meshes/Props/SM_Fruits.SM_Fruits",
        "/Game/ManagerOffice/Meshes/Props/SM_PC.SM_PC",
        "/Game/ManagerOffice/Meshes/Props/SM_MarkerMug.SM_MarkerMug",
    ]

    mesh_extents = state.sim.get_mesh_extent(state.floor_objects + state.table_objects)[
        "outputs"
    ]
    state.mesh_extents = {
        x["mesh_path"]: x["extent"] for x in mesh_extents if x["status"] == "ok"
    }

    for x in state.floor_objects:
        if x not in state.mesh_extents:
            print(f"Warning: Floor object {x} not found in the scene.")
    for x in state.table_objects:
        if x not in state.mesh_extents:
            print(f"Warning: Table object {x} not found in the scene.")

    state.floor_objects = [x for x in state.floor_objects if x in state.mesh_extents]
    state.table_objects = [x for x in state.table_objects if x in state.mesh_extents]

    state.table_height_margin_low, state.table_height_margin_high = (
        -30.0,
        50.0,
    )  # table object hit box [top-30, top+50]
    state.table_object_threshold = (
        0.75  # IoA threshold: intersection over object volume
    )

    # number of trials to sample floor objects
    state.max_floor_sampling_trials = 20
    # IoU threshold for floor object collision detection
    state.floor_object_collision_iou_thr = 0.1
    # threshold for worst addition on floor: if worse than this, skip adding floor objects
    state.worst_floor_addition = -10

    # number of trials to sample table objects
    state.max_table_sampling_trials = 20
    # IoU threshold for table object collision detection
    state.table_object_collision_iou_thr = 0.1
    # threshold for worst addition on table: if worse than this, skip adding table objects
    state.worst_table_addition = -10


def add_selection_as_floor(state, num_objects):
    objects = state.sim.list_selected()
    if objects["status"] != "ok":
        raise RuntimeError(f"Failed to get selected objects. Response: {objects}")

    new_floors = []
    for obj in objects["outputs"]:
        obj_id = obj["object_id"]
        new_floors.append((obj_id, num_objects))

    before_count = len(state.floors)
    state.floors.update(new_floors)

    print(
        f"Added {len(new_floors)} object(s) to the floor list (prev={before_count} "
        f"-> now={len(state.floors)}):\n{state.floors}"
    )


def add_selection_as_table(state, num_objects):
    objects = state.sim.list_selected()
    if objects["status"] != "ok":
        raise RuntimeError(f"Failed to get selected objects. Response: {objects}")

    new_tables = []
    for obj in objects["outputs"]:
        obj_id = obj["object_id"]
        new_tables.append((obj_id, num_objects))

    before_count = len(state.tables)
    state.tables.update(new_tables)

    print(
        f"Added {len(new_tables)} object(s) to the table list (prev={before_count} "
        f"-> now={len(state.tables)}):\n{state.tables}"
    )


def add_camera_location(state):
    cam_id = state.cam_id
    loc = state.sim.get_cam_loc(0)

    before_count = len(state.cam_locations)
    state.cam_locations.append(loc)

    print(f"New location added (prev={before_count} -> {len(state.cam_locations)}):")
    for loc in state.cam_locations:
        print(f"\t{loc}")


def get_objects_on_aabb(state, table_aabb, objs_aabb):
    table_aabb, objs_aabb = copy.deepcopy(table_aabb), copy.deepcopy(objs_aabb)
    object_list = []
    target_center, target_extent = table_aabb["center"], table_aabb["extent"]

    # we compute the space above the table
    state.table_height_margin_low, state.table_height_margin_high = -30.0, 50.0
    target_center[2] = (
        target_center[2]
        + target_extent[2]
        + (state.table_height_margin_low + state.table_height_margin_high) / 2.0
    )
    target_extent[2] = (
        state.table_height_margin_high - state.table_height_margin_low
    ) / 2.0

    tgt_min = np.array(target_center) - np.array(target_extent)
    tgt_max = np.array(target_center) + np.array(target_extent)

    for aabb in objs_aabb:
        if aabb["status"] != "ok" or aabb["object_id"] == table_aabb["object_id"]:
            continue
        aabb["extent"] = [max(x, 1e-6) for x in aabb["extent"]]
        obj_min = np.array(aabb["center"]) - np.array(aabb["extent"])
        obj_max = np.array(aabb["center"]) + np.array(aabb["extent"])

        inter_min = np.maximum(obj_min, tgt_min)
        inter_max = np.minimum(obj_max, tgt_max)
        inter_extent = np.maximum(0.0, inter_max - inter_min)
        inter_vol = np.prod(inter_extent)

        obj_vol = np.prod(2 * np.array(aabb["extent"]))

        if inter_vol / obj_vol >= state.table_object_threshold:
            object_list.append(aabb["object_id"])

    return object_list


def clear_table_objects(state, table_id, objs_aabb):
    objs_aabb = copy.deepcopy(objs_aabb)
    table_aabb = [x for x in objs_aabb if x["object_id"] == table_id][0]
    objects_on_table = get_objects_on_aabb(state, table_aabb, objs_aabb)
    for obj_id in objects_on_table:
        state.sim.del_obj(obj_id)


def collide(center1, extent1, center2, extent2, thr):
    center1, extent1 = np.array(center1), np.array(extent1)
    center2, extent2 = np.array(center2), np.array(extent2)

    min1, max1 = center1 - extent1, center1 + extent1
    min2, max2 = center2 - extent2, center2 + extent2

    inter_min = np.maximum(min1, min2)
    inter_max = np.minimum(max1, max2)
    inter_extent = np.maximum(0.0, inter_max - inter_min)
    inter_vol = np.prod(inter_extent)

    vol1, vol2 = np.prod(2 * extent1), np.prod(2 * extent2)
    union_vol = vol1 + vol2 - inter_vol

    iou = inter_vol / union_vol if union_vol > 0 else 0.0
    return iou >= thr


def compute_addition_from_collision(state, objs_aabb, sampling):
    addition = len(sampling)

    # first check mutual collisions
    for obj1 in sampling:
        for obj2 in sampling:
            if obj1 >= obj2:
                continue
            if collide(
                sampling[obj1]["center"],
                sampling[obj1]["extent"],
                sampling[obj2]["center"],
                sampling[obj2]["extent"],
                state.floor_object_collision_iou_thr,
            ):
                return -1e5, []

    tables = [x[0] for x in state.tables]
    all_collided_objects = []
    for obj in sampling:
        collided_objects = [
            x
            for x in objs_aabb
            if collide(
                x["center"],
                x["extent"],
                sampling[obj]["center"],
                sampling[obj]["extent"],
                state.floor_object_collision_iou_thr,
            )
        ]
        for x in collided_objects:
            if x["object_id"] in tables:
                return -1e5, []
        addition -= len(collided_objects)
        all_collided_objects.extend([x["object_id"] for x in collided_objects])
    return addition, all_collided_objects


def sample_floor_objects(state, floor_id, num_objects, objs_aabb):
    floor_aabb = state.sim.get_obj_aabb(floor_id)["outputs"][0]
    target_center, target_extent = np.array(floor_aabb["center"]), np.array(
        floor_aabb["extent"]
    )
    target_extent[0] *= 0.9
    target_extent[1] *= 0.9

    best_sampling, best_addition, best_collisions = None, -1e6, None
    for _ in range(state.max_floor_sampling_trials):
        sampling = {}
        sampled_object_ids = [
            state.floor_objects[i]
            for i in np.random.choice(
                len(state.floor_objects), num_objects, replace=False
            )
        ]
        for soi in sampled_object_ids:
            horizontal_location = target_center[:2] + np.random.uniform(
                -target_extent[:2] * 0.5, target_extent[:2] * 0.5
            )
            vertical_location = target_center[2] + target_extent[2]
            sampling[soi] = dict(
                center=list(horizontal_location) + [vertical_location],
                extent=state.mesh_extents[soi],
            )
        addition, collisions = compute_addition_from_collision(
            state, objs_aabb, sampling
        )
        if addition > best_addition:
            best_addition = addition
            best_sampling = sampling
            best_collisions = collisions
    if best_addition < state.worst_floor_addition:
        # print(f"Best addition: {best_addition}, collisions: {best_collisions}")
        return None

    for obj_id in best_collisions:
        state.sim.del_obj(obj_id)
        # print(f"del {obj_id}")
    for obj_id in best_sampling:
        loc = best_sampling[obj_id]["center"]
        rot = [0.0, float(np.random.uniform(0, 360)), 0.0]
        state.sim.add_obj(f"{obj_id.split('.')[-1]}_{random_uuid()}", obj_id, loc, rot)
        # print(f"add {obj_id}, {loc}, {rot}")


def sample_table_objects(state, table_id, num_objects, objs_aabb):
    table_aabb = state.sim.get_obj_aabb(table_id)["outputs"][0]
    target_center, target_extent = np.array(table_aabb["center"]), np.array(
        table_aabb["extent"]
    )
    target_extent[0] *= 0.9
    target_extent[1] *= 0.9

    best_sampling, best_addition, best_collisions = None, -1e6, None
    for _ in range(state.max_table_sampling_trials):
        sampling = {}
        sampled_object_ids = [
            state.table_objects[i]
            for i in np.random.choice(
                len(state.table_objects), num_objects, replace=False
            )
        ]
        for soi in sampled_object_ids:
            horizontal_location = target_center[:2] + np.random.uniform(
                -target_extent[:2] * 0.5, target_extent[:2] * 0.5
            )
            vertical_location = target_center[2] + target_extent[2]
            sampling[soi] = dict(
                center=list(horizontal_location) + [vertical_location],
                extent=state.mesh_extents[soi],
            )
        addition, collisions = compute_addition_from_collision(
            state, objs_aabb, sampling
        )
        if addition > best_addition:
            best_addition = addition
            best_sampling = sampling
            best_collisions = collisions
    if best_addition < state.worst_table_addition:
        print(f"Best addition: {best_addition}, collisions: {best_collisions}")
        return None

    for obj_id in best_collisions:
        state.sim.del_obj(obj_id)
        print(f"del {obj_id}")
    for obj_id in best_sampling:
        loc = best_sampling[obj_id]["center"]
        rot = [0.0, float(np.random.uniform(0, 360)), 0.0]
        state.sim.add_obj(f"{obj_id.split('.')[-1]}_{random_uuid()}", obj_id, loc, rot)
        print(f"add {obj_id}, {loc}, {rot}")


def sample_random_placement(state):
    objs_aabb = state.sim.get_obj_aabb()["outputs"]

    for floor_id, num_objects in state.floors:
        sample_floor_objects(state, floor_id, num_objects, objs_aabb)

    for table_id, num_objects in state.tables:
        clear_table_objects(state, table_id, objs_aabb)
        sample_table_objects(state, table_id, num_objects, objs_aabb)


def get_random_camera_rotations(state):
    def sample_rotation():
        pitch = float(np.random.uniform(state.min_pitch, state.max_pitch))
        yaw = float(np.random.uniform(0, 360))
        roll = 0.0
        return [pitch, yaw, roll]

    return [sample_rotation() for _ in range(state.random_viewpoints_per_location)]


def add_random_camera_height_offset(loc, state):
    offset = float(
        np.random.uniform(
            -state.random_camera_height_offset, state.random_camera_height_offset
        )
    )
    new_loc = loc.copy()
    new_loc[2] += offset
    return new_loc


def set_camera_location_and_rotation(scene_state, cam_loc_final, cam_rot):
    cam_id = scene_state.cam_id
    sim = scene_state.sim

    sim.set_cam_loc(cam_id, cam_loc_final)
    sim.set_cam_rot(cam_id, cam_rot)


def save_state(scene_state):
    save_state = {}
    for k in scene_state:
        if isinstance(scene_state[k], LychSim):
            save_state[k] = str(type(scene_state[k]))
        elif isinstance(scene_state[k], set):
            save_state[k] = list(scene_state[k])
        else:
            save_state[k] = scene_state[k]

    save_path = os.path.join(scene_state.save_path, scene_state.scene_name)
    os.makedirs(save_path, exist_ok=True)

    with open(os.path.join(save_path, "state.json"), "w") as f:
        json.dump(save_state, f, indent=4)


def capture_and_save(scene_state, view_name, camera_warmup_steps=10):
    scene_output_path = os.path.join(
        scene_state.save_path, scene_state.scene_name, view_name
    )
    os.makedirs(scene_output_path, exist_ok=True)

    scene_state.sim.warmup_cam(scene_state.cam_id, camera_warmup_steps)
    image = scene_state.sim.get_cam_lit(scene_state.cam_id)
    image.save(os.path.join(scene_output_path, "lit.png"))

    seg = scene_state.sim.get_cam_seg(scene_state.cam_id)
    seg.save(os.path.join(scene_output_path, "seg.png"))

    depth = scene_state.sim.get_cam_depth(scene_state.cam_id)
    np.save(os.path.join(scene_output_path, "depth.npy"), depth)

    # Save OpenCV-space point map (X right, Y down, Z forward), shape (H, W, 3), float32
    point_map = scene_state.sim.get_cam_pointmap(scene_state.cam_id, space="opencv")["opencv"]
    np.save(os.path.join(scene_output_path, "pointmap_opencv.npy"), point_map)

    normal = scene_state.sim.get_cam_normal(scene_state.cam_id)
    normal.save(os.path.join(scene_output_path, "normal.png"))

    annots_obj = scene_state.sim.get_obj_annots()
    with open(os.path.join(scene_output_path, "object_annots.json"), "w") as f:
        json.dump(annots_obj, f)

    annots_cam = scene_state.sim.get_cam_annots(scene_state.cam_id)
    cam_entry = annots_cam["outputs"][0]
    fov = cam_entry["fov"]
    w = cam_entry["width"]
    h = cam_entry["height"]
    fovx = np.deg2rad(fov)
    fx = 0.5 * w / np.tan(0.5 * fovx)
    fovy = 2.0 * np.arctan((h / float(w)) * np.tan(0.5 * fovx))
    fy = 0.5 * h / np.tan(0.5 * fovy)
    cam_entry["fxfycxcy"] = [fx, fy, w / 2.0, h / 2.0]
    with open(os.path.join(scene_output_path, "camera_annots.json"), "w") as f:
        json.dump(annots_cam, f)

    scene_state.sim.clear_annot_comps()


def visualize_bbox(img, corners_2d, edges, color=(255, 255, 0, 255), thickness=2):
    for i, j in edges:
        pt1 = (int(corners_2d[i, 0]), int(corners_2d[i, 1]))
        pt2 = (int(corners_2d[j, 0]), int(corners_2d[j, 1]))
        cv2.line(img, pt1, pt2, color, thickness)
    plt.imshow(img)
    return img


def draw_bbox_3d(img, center, extent, c2w, fov):
    if isinstance(img, Image.Image):
        img = np.array(img)
    vis_img = np.array(img).copy()
    corners, edges = get_bbox3d(center=center, extent=extent)
    pts2d, in_front = project_3d_to_2d(corners, c2w, fov, 1920, 1080)
    vis_img = visualize_bbox(vis_img, pts2d, edges, color=(0, 255, 0, 255))
    return Image.fromarray(vis_img)


def random_uuid(length=4):
    return "".join(
        np.random.choice(list("abcdefghijklmnopqrstuvwxyz0123456789"), size=length)
    )
