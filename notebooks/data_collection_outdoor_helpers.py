import json
import math
import os
import random
import secrets
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image
from scipy.stats import truncnorm
from shapely.geometry import Polygon

from lychsim.utils.rectangle import create_rectangle
from lychsim.utils.spline import create_spline
from lychsim.utils.io import mask_to_rle

from data_collection_helpers import (
    add_camera_location,
    EasyDict,
    set_camera_location_and_rotation,
)


def init_sampling_params(state):
    state.vehicle_objects = [
        "/Game/Fab/Tricycle/02.02",
        "/Game/NYC_East_Village/Blueprint/BP_Suv_Car_01.BP_Suv_Car_01",
        "/Game/CitySampleVehicles/vehicle12_Car/BP_vehicle12_Car.BP_vehicle12_Car",
        "/Game/CitySampleVehicles/vehicle13_Car/BP_vehicle13_Car.BP_vehicle13_Car",
        "/Game/CitySampleVehicles/Blueprint/BP_Vehicle.BP_Vehicle",
        "/Game/Tokyo_Street/Bleuprint/BP_Japan_Minivan.BP_Japan_Minivan",
        "/Game/Tokyo_Street/Bleuprint/BP_Mini_Truck.BP_Mini_Truck",
    ]
    state.pedestrian_objects = []
    state.road_objects = [
        "/Game/NYC_East_Village/Models/Props/SM_Cone_01.SM_Cone_01",
        "/Game/NYC_East_Village/Models/Props/SM_Cone_02.SM_Cone_02",
        "/Game/WarehouseProps_Bundle/Models/Skeletal/SKM_Cart_01a.SKM_Cart_01a",
        "/Game/WarehouseProps_Bundle/Models/Skeletal/SKM_Pallet_Truck_01a.SKM_Pallet_Truck_01a",
        "/Game/WarehouseProps_Bundle/Models/Skeletal/SKM_Reach_Truck_01a.SKM_Reach_Truck_01a",
        "/Game/Barriers/MetalBarrier/Meshes/SM_Metallic_Barrier_01.SM_Metallic_Barrier_01",
    ]
    state.sidewalk_objects = [
        "/Game/NYC_East_Village/Models/Props/SM_Fire_Hydrant.SM_Fire_Hydrant",
        "/Game/NYC_East_Village/Models/Props/SM_Garbage_Bag_01.SM_Garbage_Bag_01",
        "/Game/NYC_East_Village/Models/Props/SM_Garbage_Bag_02.SM_Garbage_Bag_02",
        "/Game/NYC_East_Village/Models/Props/SM_Mailbox.SM_Mailbox",
        "/Game/WarehouseProps_Bundle/Models/SM_Bag_02a_Stack.SM_Bag_02a_Stack",
    ]

    state.lock_rotation_categories = [
        "tricycle", "signboard", "bicycle", "traffic_cone", "fire_hydrant",
        "mailbox", "traffic_sign", "trash_can", "scooter", "portable_toilet",
        "hand_cart", "pallet_truck", "reach_truck", "bag_stack", "beer_keg",
        "barrel", "box_stack", "cable_drum", "fire_extinguisher", "rack",
        "atm", "hot_dog_stand", "post_box", "patio_umbrella", "traffic_barrier",
        "traffic_drum", "bucket", "parking_meter", "table", "vending_machine",
        "flower_pot", "recycling_bin", "fruit_shelf", "parasol", "fruit_stall",
        "payphone", "beach_umbrella", "bicycle_rack", "surfboard", "tent",
        "palm_tree"
    ]

    state.obj_sampling_params = dict()
    df = pd.read_csv("outdoor_objects_1103_params.csv")
    for _, row in df.iterrows():
        values = row.to_dict()
        state.obj_sampling_params[values["path"]] = values

    state.mesh_extents = {}
    state.mesh_2d_offset = {}
    for obj_path in state.obj_sampling_params:
        state.mesh_extents[obj_path] = [
            state.obj_sampling_params[obj_path]["extent_x"],
            state.obj_sampling_params[obj_path]["extent_y"],
            state.obj_sampling_params[obj_path]["extent_z"],
        ]
        state.mesh_2d_offset[obj_path] = [
            state.obj_sampling_params[obj_path]["mesh_2d_offset_x"],
            state.obj_sampling_params[obj_path]["mesh_2d_offset_y"],
        ]

    cate_mapping = json.load(open("category_mapping.json"))
    for x in state.obj_sampling_params:
        types = cate_mapping[state.obj_sampling_params[x]["category"]]
        if "0" in types:
            state.vehicle_objects.append(x)
        if "1" in types:
            state.pedestrian_objects.append(x)
        if "2" in types:
            state.road_objects.append(x)
        if "3" in types:
            state.sidewalk_objects.append(x)

    print(f"Initialized {len(state.vehicle_objects)} vehicle objects")
    print(f"Initialized {len(state.pedestrian_objects)} pedestrian objects")
    print(f"Initialized {len(state.road_objects)} road objects")
    print(f"Initialized {len(state.sidewalk_objects)} sidewalk objects")

    state.sample_height_offset = 0.0

    state.collide_iou_thr = 0.0
    state.collision_extent_expand_rate = 1.1

    state.sampling_records = []

    state.debug = False


def load_procedural_rules(state, rules_path):
    state.procedural_rules = {}
    state.procedural_rules['vehicle'] = json.load(open(os.path.join(rules_path, 'vehicle_traj.json')))
    state.procedural_rules['pedestrian'] = json.load(open(os.path.join(rules_path, 'pedestrian_traj.json')))
    state.procedural_rules['road_object'] = json.load(open(os.path.join(rules_path, 'road.json')))
    state.procedural_rules['sidewalk_object'] = json.load(open(os.path.join(rules_path, 'sidewalk.json')))

    splines = [
        create_spline(
            loc0=x['start']['location'], rot0=x['start']['rotation'],
            loc1=x['end']['location'], rot1=x['end']['rotation'])
        for x in state.procedural_rules['vehicle']
    ]
    state.procedural_rules['vehicle_splines'] = [s.length for s in splines], splines

    splines = [
        create_spline(
            loc0=x['start']['location'], rot0=x['start']['rotation'],
            loc1=x['end']['location'], rot1=x['end']['rotation'])
        for x in state.procedural_rules['pedestrian']
    ]
    state.procedural_rules['pedestrian_splines'] = [s.length for s in splines], splines

    regions = [
        create_rectangle(x['bounds'])
        for x in state.procedural_rules['road_object']
    ]
    state.procedural_rules['road_regions'] = [r.area for r in regions], regions

    regions = [
        create_rectangle(x['bounds'])
        for x in state.procedural_rules['sidewalk_object']
    ]
    state.procedural_rules['sidewalk_regions'] = [r.area for r in regions], regions


def random_uuid():
    return secrets.token_hex(4)


def add_camera(state, cam_id):
    loc = state.sim.get_cam_loc(cam_id)
    rot = state.sim.get_cam_rot(cam_id)

    before_count = len(state.cam_locations)
    state.cam_locations.append(loc + rot)

    print(f"New location added (prev={before_count} -> {len(state.cam_locations)}):")


def place_object_at_location(state, obj_id, obj_path, location, rotation, skip_if_colliding=False, lock_rotation=False):
    cate = state.obj_sampling_params[obj_path]["category"]
    lock_rotation = (cate in state.lock_rotation_categories) and lock_rotation

    res = state.sim.add_obj(
        obj_id, obj_path, location, rotation,
        scale=state.obj_sampling_params[obj_path]["scale"],
        skip_if_colliding=skip_if_colliding, lock_rotation=lock_rotation)
    if res["status"] != "ok":
        return False
    return True


def get_corners(center, extent, yaw):
    corners = np.array([
        [-extent[0], -extent[1]],
        [extent[0], -extent[1]],
        [extent[0], extent[1]],
        [-extent[0], extent[1]],
    ])
    R = np.array([
        [math.cos(yaw), -math.sin(yaw)],
        [math.sin(yaw), math.cos(yaw)],
    ])
    corners = np.dot(R, corners.T).T
    corners += np.array([center[0], center[1]])
    zmin, zmax = center[2] - extent[2], center[2] + extent[2]

    corners3d = np.concatenate([
        np.concatenate([corners, np.full((4, 1), zmin)], axis=1),
        np.concatenate([corners, np.full((4, 1), zmax)], axis=1),
    ], axis=0)

    return corners3d, Polygon(corners), zmin, zmax


def collide(center1, extent1, yaw1, center2, extent2, yaw2, thr, zmin=None):
    yaw1 = yaw1 / 180 * math.pi
    yaw2 = yaw2 / 180 * math.pi
    _, poly1, zmin1, zmax1 = get_corners(center1, extent1, yaw1)
    _, poly2, zmin2, zmax2 = get_corners(center2, extent2, yaw2)
    if zmin is not None:
        zmin1, zmax1 = max(zmin1, zmin), max(zmax1, zmin)
        zmin2, zmax2 = max(zmin2, zmin), max(zmax2, zmin)
    if zmax1 - zmin1 <= 1e-3 or zmax2 - zmin2 <= 1e-3:
        return False, 0.0

    if not poly1.is_valid:
        raise ValueError(f"Invalid polygon for collision detection: {center1} {extent1} {yaw1}")
    if not poly2.is_valid:
        raise ValueError(f"Invalid polygon for collision detection: {center2} {extent2} {yaw2}")

    inter_h = max(0.0, min(zmax1, zmax2) - max(zmin1, zmin2))
    if inter_h <= 0:
        return False, 0.0

    inter_area = poly1.intersection(poly2).area
    if inter_area <= 0:
        return False, 0.0

    inter_vol = inter_area * inter_h
    vol1 = poly1.area * (zmax1 - zmin1)
    vol2 = poly2.area * (zmax2 - zmin2)
    iou = inter_vol / (vol1 + vol2 - inter_vol)
    return iou >= thr, iou


def collide_sampling(state, obj1, obj2, thr=0.0):
    center1 = obj1["loc"].copy()
    extent1 = state.mesh_extents[obj1["obj_path"]].copy()
    yaw1 = obj1["rot"][1] + state.obj_sampling_params[obj1["obj_path"]]["rotation yaw"]
    center1[2] += extent1[2]

    center2 = obj2["loc"].copy()
    extent2 = state.mesh_extents[obj2["obj_path"]].copy()
    yaw2 = obj2["rot"][1] + state.obj_sampling_params[obj2["obj_path"]]["rotation yaw"]
    center2[2] += extent2[2]

    extent1 = [e * state.collision_extent_expand_rate for e in extent1]
    extent2 = [e * state.collision_extent_expand_rate for e in extent2]

    return collide(center1, extent1, yaw1, center2, extent2, yaw2, thr)


def sample_vehicles(state, num_vehicles, prev_sampling, bg_annots, lock_rotation):
    lengths, splines = state.procedural_rules['vehicle_splines']

    sampling = []
    object_paths = random.choices(state.vehicle_objects, k=num_vehicles)
    for sop in object_paths:
        spline = random.choices(splines, weights=lengths, k=1)[0]
        loc, rot = spline.sample(t=random.uniform(0, 1))
        rot[1] -= 90 - state.obj_sampling_params[sop]["rotation yaw"]

        addition = dict(loc=loc, rot=rot, obj_path=sop, extent=state.mesh_extents[sop])

        for prev in prev_sampling + sampling:
            collided, iou = collide_sampling(state, addition, prev)
            if collided:
                if state.debug:
                    draw_debug_bbox3d(state, addition, color="red")
                break
        else:
            if state.debug:
                draw_debug_bbox3d(state, addition, color="green")
            sampling.append(addition)

    successful_sampling = []
    for obj in sampling:
        loc = obj['loc'].copy()
        rot = obj['rot'].copy()
        loc[0] += state.mesh_2d_offset[obj['obj_path']][0]
        loc[1] += state.mesh_2d_offset[obj['obj_path']][1]
        loc[2] += state.sample_height_offset
        obj_id = obj['obj_path'].split('.')[-1] + "_" + random_uuid()
        obj["object_id"] = obj_id
        success = place_object_at_location(
            state, obj_id, obj['obj_path'], loc, rot, skip_if_colliding=True, lock_rotation=lock_rotation)
        if success:
            successful_sampling.append(obj)

    print(f"[sample_vehicles] Spawned {len(successful_sampling)} / {len(sampling)} vehicles")
    return prev_sampling + successful_sampling


def sample_pedestrians(state, num_pedestrians, prev_sampling, bg_annots, lock_rotation):
    return prev_sampling


def sample_road_objects(state, num_road_objects, prev_sampling, bg_annots, lock_rotation):
    areas, regions = state.procedural_rules['road_regions']

    sampling = []
    object_paths = random.choices(state.road_objects, k=num_road_objects)
    for sop in object_paths:
        region = random.choices(regions, weights=areas, k=1)[0]
        loc, rot = region.sample()
        rot[1] -= 90 - state.obj_sampling_params[sop]["rotation yaw"]

        addition = dict(loc=loc, rot=rot, obj_path=sop, extent=state.mesh_extents[sop])

        for prev in prev_sampling + sampling:
            collided, iou = collide_sampling(state, addition, prev)
            if collided:
                if state.debug:
                    draw_debug_bbox3d(state, addition, color="red")
                break
        else:
            if state.debug:
                draw_debug_bbox3d(state, addition, color="green")
            sampling.append(addition)

    successful_sampling = []
    for obj in sampling:
        loc = obj['loc'].copy()
        rot = obj['rot'].copy()
        loc[0] += state.mesh_2d_offset[obj['obj_path']][0]
        loc[1] += state.mesh_2d_offset[obj['obj_path']][1]
        loc[2] += state.sample_height_offset
        obj_id = obj['obj_path'].split('.')[-1] + "_" + random_uuid()
        obj["object_id"] = obj_id
        success = place_object_at_location(
            state, obj_id, obj['obj_path'], loc, rot, skip_if_colliding=True, lock_rotation=lock_rotation)
        if success:
            successful_sampling.append(obj)

    print(f"[sample_road_objects] Spawned {len(successful_sampling)} / {len(sampling)} objects")
    return prev_sampling + successful_sampling


def sample_sidewalk_objects(state, num_sidewalk_objects, prev_sampling, bg_annots, lock_rotation):
    areas, regions = state.procedural_rules['sidewalk_regions']

    sampling = []
    object_paths = random.choices(state.sidewalk_objects, k=num_sidewalk_objects)
    for sop in object_paths:
        region = random.choices(regions, weights=areas, k=1)[0]
        loc, rot = region.sample()
        rot[1] -= 90 - state.obj_sampling_params[sop]["rotation yaw"]

        addition = dict(loc=loc, rot=rot, obj_path=sop, extent=state.mesh_extents[sop])

        for prev in prev_sampling + sampling:
            collided, iou = collide_sampling(state, addition, prev)
            if collided:
                if state.debug:
                    draw_debug_bbox3d(state, addition, color="red")
                break
        else:
            if state.debug:
                draw_debug_bbox3d(state, addition, color="green")
            sampling.append(addition)

    successful_sampling = []
    for obj in sampling:
        loc = obj['loc'].copy()
        rot = obj['rot'].copy()
        loc[0] += state.mesh_2d_offset[obj['obj_path']][0]
        loc[1] += state.mesh_2d_offset[obj['obj_path']][1]
        loc[2] += state.sample_height_offset
        obj_id = obj['obj_path'].split('.')[-1] + "_" + random_uuid()
        obj["object_id"] = obj_id
        success = place_object_at_location(
            state, obj_id, obj['obj_path'], loc, rot, skip_if_colliding=True, lock_rotation=lock_rotation)
        if success:
            successful_sampling.append(obj)

    print(f"[sample_sidewalk_objects] Spawned {len(successful_sampling)} / {len(sampling)} objects")
    return prev_sampling + successful_sampling


def sample_random_placement(state, num_vehicles=5, num_pedestrians=10, num_road_objects=50, num_sidewalk_objects=50, lock_rotation=False):
    obj_annots = state.sim.get_obj_annots()["outputs"]
    bg_annots = [
        x for x in obj_annots
        if (
            x["bounds_tight"]["extent"][0] > 1e-3 and
            x["bounds_tight"]["extent"][1] > 1e-3 and
            x["bounds_tight"]["extent"][2] > 1e-3
        )
    ]

    sampling = []
    sampling = sample_vehicles(state, num_vehicles, sampling, bg_annots, lock_rotation)
    sampling = sample_pedestrians(state, num_pedestrians, sampling, bg_annots, lock_rotation)
    sampling = sample_road_objects(state, num_road_objects, sampling, bg_annots, lock_rotation)
    sampling = sample_sidewalk_objects(state, num_sidewalk_objects, sampling, bg_annots, lock_rotation)

    return sampling


def is_stable(annots_old, annots_new, thr=1e-2):
    assert annots_old["status"] == "ok"
    assert annots_new["status"] == "ok"

    annots_old_dict = {x["object_id"]: x for x in annots_old["outputs"]}
    annots_new_dict = {x["object_id"]: x for x in annots_new["outputs"]}
    moving_objects = []
    for k in annots_old_dict:
        if k not in annots_new_dict:
            continue
        if "FirstPersonCharacter" in k:
            continue
        old_loc = np.array(annots_old_dict[k]["location"])
        new_loc = np.array(annots_new_dict[k]["location"])
        dist = np.max(np.abs(old_loc - new_loc))
        if dist > thr:
            # print('[is_stable]', k, old_loc, new_loc, dist)
            moving_objects.append(k)
        old_rot = np.array(annots_old_dict[k]["rotation"])
        new_rot = np.array(annots_new_dict[k]["rotation"])
        dist = np.max(np.abs(old_rot - new_rot))
        if dist > thr:
            # print('[is_stable]', k, old_rot, new_rot, dist)
            moving_objects.append(k)
    if len(moving_objects) > 0:
        return False, moving_objects
    return True, moving_objects


def capture_and_save(scene_state, view_name, camera_warmup_steps=100, calculate_occlusion=True, sampling=[], max_wait=10, stable_thr=1.0, del_wait=10, lighting={}, fog={}):
    scene_output_path = os.path.join(
        scene_state.save_path, scene_state.scene_name, view_name
    )
    os.makedirs(scene_output_path, exist_ok=True)

    annots_obj = scene_state.sim.get_obj_annots()

    all_deleted = []
    for wait_idx in range(max_wait):
        time.sleep(1.0)
        annots_obj_new = scene_state.sim.get_obj_annots()
        stable, moving_objects = is_stable(annots_obj, annots_obj_new, stable_thr)
        if stable:
            break
        if wait_idx >= del_wait and wait_idx % 5 == 0:
            for obj_id in moving_objects:
                scene_state.sim.del_obj(obj_id)
                print(f"[capture_and_save] Deleted moving object: {obj_id}")
            all_deleted += moving_objects
        annots_obj = annots_obj_new
    else:
        print(f"[capture_and_save] Scene not captured: annotations not stable after {max_wait} seconds")
        return
    print(f"[capture_and_save] Scene captured: stable after {wait_idx} seconds with {len(all_deleted)} / {len(sampling)} deleted objects")

    sampling = [x for x in sampling if x["object_id"] not in all_deleted]

    image = scene_state.sim.get_cam_lit(scene_state.cam_id, camera_warmup_steps)
    image.save(os.path.join(scene_output_path, "lit.png"))

    seg = scene_state.sim.get_cam_seg(scene_state.cam_id)
    seg.save(os.path.join(scene_output_path, "seg.png"))

    depth = scene_state.sim.get_cam_depth(scene_state.cam_id)
    np.save(os.path.join(scene_output_path, "depth.npy"), depth)

    point_map = scene_state.sim.get_cam_pointmap(scene_state.cam_id, space="opencv")["opencv"]
    np.save(os.path.join(scene_output_path, "pointmap_opencv.npy"), point_map)

    normal = scene_state.sim.get_cam_normal(scene_state.cam_id)
    normal.save(os.path.join(scene_output_path, "normal.png"))

    annots_obj = scene_state.sim.get_obj_annots()

    occlusion_data = {}
    if calculate_occlusion:
        seg_np = np.asarray(seg.convert("RGB"))

        for obj_id in [x["object_id"] for x in sampling]:
            obj_info_list = [x for x in annots_obj["outputs"] if x["object_id"] == obj_id]
            if len(obj_info_list) == 0:
                continue
            obj_info = obj_info_list[0]

            color = obj_info["color"][:3]
            obj_mask = np.all(seg_np == np.array(color), axis=-1)

            if np.sum(obj_mask) <= 0:
                continue

            zbuf = scene_state.sim.get_cam_zbuffer(scene_state.cam_id, [obj_id])

            if not isinstance(zbuf, np.ndarray) or zbuf.ndim != 3 or zbuf.shape[0] == 0:
                print(f"[get_cam_zbuffer] Invalid z-buffer for object {obj_id}: {zbuf}")
                continue

            z = zbuf[0]  # HxW
            z_mask = np.isfinite(z) & (z < 65500)
            total = z_mask.sum()
            visible_mask = int((z_mask & obj_mask).sum())
            occluded_mask = total - visible_mask

            if total == 0:
                occ_rate = 0.0
            else:
                occ_rate = occluded_mask / total

            z_mask_d = mask_to_rle(z_mask.astype(np.uint8))
            occlusion_data[obj_id] = (occ_rate, z_mask_d)

    for obj in sampling:
        annots = [x for x in annots_obj['outputs'] if x['object_id'] == obj['object_id']]
        if len(annots) == 0:
            continue
        if isinstance(obj["loc"], np.ndarray):
            obj["loc"] = obj["loc"].tolist()
        annots[0]["sampling_info"] = obj
        annots[0]["sampled_by_us"] = True

    for annot in annots_obj["outputs"]:
        if "sampled_by_us" not in annot:
            annot["sampled_by_us"] = False

        if annot["asset_path"] in scene_state.obj_sampling_params:
            annot["sampling_params"] = scene_state.obj_sampling_params[annot["asset_path"]]
            annot["category"] = scene_state.obj_sampling_params[annot["asset_path"]]["category"]
            if len(annot["color"]):
                annot["description"] = f"{annot['color']} {annot['category']}"
            else:
                annot["description"] = f"{annot['category']}"

    for obj_id in occlusion_data:
        obj_annot = [x for x in annots_obj['outputs'] if x['object_id'] == obj_id][0]
        obj_annot['occlusion_rate'] = occlusion_data[obj_id][0]
        obj_annot['zbuffer_mask'] = occlusion_data[obj_id][1]

    annots_obj["sampling"] = sampling

    # save scene state
    annots_obj["scene_state"] = {}
    scene_state_save_keys = [
        'cam_id', 'cam_locations', 'vehicle_objects', 'pedestrian_objects', 'road_objects', 'sidewalk_objects',
        'obj_sampling_params', 'mesh_extents', 'mesh_2d_offset', 'sample_height_offset', 'collide_iou_thr',
        'collision_extent_expand_rate', 'sampling_records', 'debug', 'save_path', 'scene_name', 'procedural_rules']
    for k in scene_state_save_keys:
        if k == "procedural_rules":
            annots_obj["scene_state"][k] = {m: scene_state[k][m] for m in ["vehicle", "pedestrian", "road_object", "sidewalk_object"]}
        else:
            annots_obj["scene_state"][k] = scene_state[k]

    annots_obj["lighting"] = lighting
    annots_obj["fog"] = fog
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


def debug_save_path(scene_state, save_path):
    lit = np.array(Image.open(os.path.join(save_path, "lit.png")).convert("RGB"))
    seg = np.array(Image.open(os.path.join(save_path, "seg.png")).convert("RGB"))

    depth = np.load(os.path.join(save_path, "depth.npy"))
    depth = np.clip(depth, 0.0, 4000.0)
    depth = depth / depth.max()
    cmap = plt.get_cmap('Spectral_r')
    depth_img = np.clip(np.rint(cmap(depth)[:, :, :3] * 255), 0, 255).astype(np.uint8)
    depth_img = Image.fromarray(depth_img)

    point_map = np.load(os.path.join(save_path, "pointmap_opencv.npy"))
    pm_z = np.clip(point_map[:, :, 2], 0.0, 4000.0)
    pm_z = pm_z / pm_z.max() if pm_z.max() > 0 else pm_z
    pm_img = np.clip(np.rint(cmap(pm_z)[:, :, :3] * 255), 0, 255).astype(np.uint8)
    pm_img = Image.fromarray(pm_img)

    annots = json.load(open(os.path.join(save_path, "object_annots.json")))["outputs"]

    vehicle_types = [x.split('.')[-1] for x in scene_state.vehicle_objects]
    vehicles = [x for x in annots if "_".join(x["object_id"].split("_")[:-1]) in vehicle_types]
    max_area, mask = 0, None
    for v in vehicles:
        v_seg = np.all(seg == np.array(v["color"][:3]), axis=-1)
        if np.sum(v_seg) > max_area:
            max_area = np.sum(v_seg)
            mask = v_seg
    green = np.zeros_like(lit)
    if max_area <= 0:
        mask = np.zeros_like(depth, dtype=bool)
    else:
        green[mask, :] = [0, 255, 0]
    obj_img = np.array(Image.blend(Image.fromarray(lit), Image.fromarray(green), alpha=0.5))

    black = np.zeros_like(lit)
    vis_image = np.concatenate([
        np.concatenate([lit, depth_img, pm_img], axis=1),
        np.concatenate([seg, obj_img, black], axis=1),
    ], axis=0)
    return Image.fromarray(vis_image)


def draw_debug_bbox3d(scene_state, obj, color="green"):
    yaw_bias = scene_state.obj_sampling_params[obj["obj_path"]]["rotation yaw"]
    yaw = (obj["rot"][1] - yaw_bias) / 180 * math.pi
    # yaw = obj["rot"][1] / 180 * math.pi
    extents = scene_state.mesh_extents[obj["obj_path"]]
    loc = obj["loc"].copy()
    loc[0] += scene_state.mesh_2d_offset[obj["obj_path"]][0]
    loc[1] += scene_state.mesh_2d_offset[obj["obj_path"]][1]
    loc[2] += extents[2]
    corners, _, _, _ = get_corners(loc, extents, yaw)
    scene_state.sim.draw_debug_line_pts([corners[i] for i in [0,1,2,3,0]], color=color)
    scene_state.sim.draw_debug_line_pts([corners[i] for i in [4,5,6,7,4]], color=color)
    scene_state.sim.draw_debug_line_pts([corners[i] for i in [0,1,5,4,0]], color=color)
    scene_state.sim.draw_debug_line_pts([corners[i] for i in [2,3,7,6,2]], color=color)
    scene_state.sim.draw_debug_line_pts([corners[i] for i in [1,6]], color=color)
    scene_state.sim.draw_debug_line_pts([corners[i] for i in [2,5]], color=color)


def visualize_procedural_rules(scene_state, z_offset=10.0, thickness=5.0):
    # vehicle
    splines = scene_state.procedural_rules["vehicle_splines"][1]
    for spline in splines:
        locations = [spline.sample(t)[0] for t in np.linspace(0, 1, 10)]
        locations = [[loc[0], loc[1], loc[2] + z_offset] for loc in locations]
        scene_state.sim.draw_debug_line_pts(locations, color="green", thickness=thickness)

    # pedestrian
    splines = scene_state.procedural_rules["pedestrian_splines"][1]
    for spline in splines:
        locations = [spline.sample(t)[0] for t in np.linspace(0, 1, 10)]
        locations = [[loc[0], loc[1], loc[2] + z_offset] for loc in locations]
        scene_state.sim.draw_debug_line_pts(locations, color="cyan", thickness=thickness)

    # road
    regions = scene_state.procedural_rules["road_regions"][1]
    for region in regions:
        corners = [region.corners[i] for i in [0,1,2,3,0]]
        corners = [[loc[0], loc[1], loc[2] + z_offset] for loc in corners]
        scene_state.sim.draw_debug_line_pts(corners, color="orange", thickness=thickness)

    # sidewalk
    regions = scene_state.procedural_rules["sidewalk_regions"][1]
    for region in regions:
        corners = [region.corners[i] for i in [0,1,2,3,0]]
        corners = [[loc[0], loc[1], loc[2] + z_offset] for loc in corners]
        scene_state.sim.draw_debug_line_pts(corners, color="yellow", thickness=thickness)


def sample_normal(mean, std, min_val, max_val):
    dist = truncnorm((min_val - mean) / std, (max_val - mean) / std, loc=mean, scale=std)
    return round(dist.rvs())


def randomize_directional_light(state, light_id):
    curr_rot = state.sim.get_obj_annots(light_id)["outputs"]
    assert len(curr_rot) != 0, f"Light {light_id} not found"

    rot = curr_rot[0]["rotation"]
    rot[1] = random.uniform(0, 360)

    temp = sample_normal(6000, 500, 5000, 7000)

    state.sim.adjust_light(light_id, rot=rot, temp=temp)
    return {"rotation": rot, "temperature": temp}
