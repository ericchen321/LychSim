import logging
import os


def test_lit(sim):
    img = sim.get_cam_lit(0, 50)
    os.makedirs("test_outputs", exist_ok=True)
    img.save(os.path.join("test_outputs", "lit.png"))
    logging.info("Lit image saved to test_outputs/lit.png")
