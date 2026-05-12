import math

import numpy as np
from chspy import CubicHermiteSpline as CHS


class CubicHermiteSpline:
    def __init__(self, loc0, rot0, loc1, rot1):
        self.loc0 = loc0
        self.rot0 = rot0
        self.loc1 = loc1
        self.rot1 = rot1

        dist = math.sqrt((loc1[0]-loc0[0])**2 + (loc1[1]-loc0[1])**2)

        self.dir0 = [-math.sin(self.rot0[1]/180*math.pi) * dist, math.cos(self.rot0[1]/180*math.pi) * dist, 0]
        self.dir1 = [-math.sin(self.rot1[1]/180*math.pi) * dist, math.cos(self.rot1[1]/180*math.pi) * dist, 0]

        self.spline = CHS(n=3)
        self.spline.add((0, self.loc0, self.dir0))
        self.spline.add((1, self.loc1, self.dir1))

    def sample(self, t):
        assert 0 <= t <= 1, f't must be in [0, 1], got {t}'
        self.spline.interpolate_anchor(t)
        anchor0, anchor1 = self.spline.get_anchors(t)
        assert anchor0[0] == t or anchor1[0] == t, f"Anchors ({anchor0[0]}, {anchor1[0]}) do not correspond to time t"
        if anchor0[0] == t:
            loc, dir = anchor0[1], anchor0[2]
        elif anchor1[0] == t:
            loc, dir = anchor1[1], anchor1[2]
        else:
            raise RuntimeError(f"Anchors ({anchor0[0]}, {anchor1[0]}) do not correspond to time t = {t}")
        yaw = math.atan2(-dir[0], dir[1])/math.pi*180
        return loc, [0, yaw, 0]

    @property
    def length(self):
        num_samples = 10
        times = np.linspace(0, 1, num_samples)
        locations = np.array([[0.0, 0.0, 0.0]] + [self.sample(t)[1] for t in times])
        distances = np.linalg.norm(locations[1:] - locations[:-1], axis=1)
        length = np.sum(distances)
        return length


def create_spline(loc0, rot0, loc1, rot1):
    return CubicHermiteSpline(loc0, rot0, loc1, rot1)
