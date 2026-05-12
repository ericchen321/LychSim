import json
import os

import numpy as np

from lychsim.utils.rectangle import create_rectangle
from lychsim.utils.spline import create_spline


def init_sampling_params(state):
    pass


def add_vehicle_rule(state):
    objs = json.loads(state.sim.client.request('lych data info'))
    if objs["status"] != "ok":
        return RuntimeError(objs["status"])
    if len(objs["outputs"]) < 2:
        return RuntimeError(
            f"Expected at least 2 objects as start and end, got {len(objs['outputs'])}")

    for i in range(0, len(objs["outputs"])-1):
        start, end = objs["outputs"][i], objs["outputs"][i+1]
        state.rules['vehicle_traj'].append(dict(start=start, end=end))
        print(
            f"Added vehicle rule (total={len(state.rules['vehicle_traj'])}):\n"
            f"{state.rules['vehicle_traj'][-1]}")

    object_ids = [x["object_id"] for x in objs["outputs"]]
    state.sim.draw_debug_line(object_ids, color='cyan')


def add_pedestrian_rule(state):
    objs = json.loads(state.sim.client.request('lych data info'))
    if objs["status"] != "ok":
        return RuntimeError(objs["status"])
    if len(objs["outputs"]) < 2:
        return RuntimeError(
            f"Expected at least 2 objects as start and end, got {len(objs['outputs'])}")

    for i in range(0, len(objs["outputs"])-1):
        start, end = objs["outputs"][i], objs["outputs"][i+1]
        state.rules['pedestrian_traj'].append(dict(start=start, end=end))
        print(
            f"Added pedestrian rule (total={len(state.rules['pedestrian_traj'])}):\n"
            f"{state.rules['pedestrian_traj'][-1]}")

    object_ids = [x["object_id"] for x in objs["outputs"]]
    state.sim.draw_debug_line(object_ids, color='green')


def add_road(state):
    objs = json.loads(state.sim.client.request('lych data info'))
    if objs["status"] != "ok":
        return RuntimeError(objs["status"])

    for i in range(len(objs["outputs"])):
        obj = objs["outputs"][i]
        state.rules['road'].append(obj)
        print(
            f"Added road (total={len(state.rules['road'])}):\n"
            f"{state.rules['road'][-1]}")


def add_sidewalk(state):
    objs = json.loads(state.sim.client.request('lych data info'))
    if objs["status"] != "ok":
        return RuntimeError(objs["status"])

    for i in range(len(objs["outputs"])):
        obj = objs["outputs"][i]
        state.rules['sidewalk'].append(obj)
        print(
            f"Added sidewalk (total={len(state.rules['sidewalk'])}):\n"
            f"{state.rules['sidewalk'][-1]}")


def save_rules(state):
    os.makedirs(state.scene_name, exist_ok=True)
    for k in state.rules:
        with open(os.path.join(state.scene_name, f'{k}.json'), 'w') as f:
            json.dump(state.rules[k], f, indent=4)


def visualize_procedural_rules(scene_state, z_offset=10.0, thickness=5.0):
    rules = {}

    splines = [
        create_spline(
            loc0=x['start']['location'], rot0=x['start']['rotation'],
            loc1=x['end']['location'], rot1=x['end']['rotation'])
        for x in scene_state.rules['vehicle_traj']
    ]
    rules['vehicle_splines'] = [s.length for s in splines], splines

    splines = [
        create_spline(
            loc0=x['start']['location'], rot0=x['start']['rotation'],
            loc1=x['end']['location'], rot1=x['end']['rotation'])
        for x in scene_state.rules['pedestrian_traj']
    ]
    rules['pedestrian_splines'] = [s.length for s in splines], splines

    regions = [
        create_rectangle(x['bounds'])
        for x in scene_state.rules['road']
    ]
    rules['road_regions'] = [r.area for r in regions], regions

    regions = [
        create_rectangle(x['bounds'])
        for x in scene_state.rules['sidewalk']
    ]
    rules['sidewalk_regions'] = [r.area for r in regions], regions

    # vehicle
    splines = rules["vehicle_splines"][1]
    for spline in splines:
        locations = [spline.sample(t)[0] for t in np.linspace(0, 1, 10)]
        locations = [[loc[0], loc[1], loc[2] + z_offset] for loc in locations]
        scene_state.sim.draw_debug_line_pts(locations, color="green", thickness=thickness)

    # pedestrian
    splines = rules["pedestrian_splines"][1]
    for spline in splines:
        locations = [spline.sample(t)[0] for t in np.linspace(0, 1, 10)]
        locations = [[loc[0], loc[1], loc[2] + z_offset] for loc in locations]
        scene_state.sim.draw_debug_line_pts(locations, color="cyan", thickness=thickness)

    # road
    regions = rules["road_regions"][1]
    for region in regions:
        corners = [region.corners[i] for i in [0,1,2,3,0]]
        corners = [[loc[0], loc[1], loc[2] + z_offset] for loc in corners]
        scene_state.sim.draw_debug_line_pts(corners, color="orange", thickness=thickness)

    # sidewalk
    regions = rules["sidewalk_regions"][1]
    for region in regions:
        corners = [region.corners[i] for i in [0,1,2,3,0]]
        corners = [[loc[0], loc[1], loc[2] + z_offset] for loc in corners]
        scene_state.sim.draw_debug_line_pts(corners, color="yellow", thickness=thickness)
