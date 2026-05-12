import json
import logging
import os


def test_add_obj(sim):
    obj_id = "demo_minivan"
    obj_path = "/Game/Japanese_Street/Models/AE_Auto/AE_Minivan_Street_AE_Minivan_Street_LOD0.AE_Minivan_Street_AE_Minivan_Street_LOD0"
    obj_loc = [-30, -170, -20]
    obj_rot = [0, -157, 0]

    res = sim.add_obj(
        obj_id, obj_path, obj_loc, obj_rot, scale=1.0,
        skip_if_colliding=True, lock_rotation=False)
    assert res["status"] == "ok", "Failed to add object to the simulation"

    img = sim.get_cam_lit(0, 50)
    os.makedirs("test_outputs", exist_ok=True)
    img.save(os.path.join("test_outputs", "lit_minivan.png"))
    logging.info("Lit image after adding object saved to test_outputs/lit_minivan.png")

