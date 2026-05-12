import math
import random

import numpy as np


class Rectangle:
    def __init__(self, bounds):
        self.center = bounds["center"]
        self.extent = bounds["extent"]
        self.padding = 1e-1

    def sample(self):
        x = random.uniform(
            self.center[0] - self.extent[0],
            self.center[0] + self.extent[0]
        )
        y = random.uniform(
            self.center[1] - self.extent[1],
            self.center[1] + self.extent[1]
        )
        z = self.center[2] + self.extent[2] + self.padding
        return [x, y, z], [0, random.uniform(0, 360), 0]

    @property
    def area(self):
        return (2 * self.extent[0]) * (2 * self.extent[1])

    @property
    def corners(self):
        return [
            [
                self.center[0] - self.extent[0],
                self.center[1] - self.extent[1],
                self.center[2] + self.extent[2]
            ],
            [
                self.center[0] + self.extent[0],
                self.center[1] - self.extent[1],
                self.center[2] + self.extent[2]
            ],
            [
                self.center[0] + self.extent[0],
                self.center[1] + self.extent[1],
                self.center[2] + self.extent[2]
            ],
            [
                self.center[0] - self.extent[0],
                self.center[1] + self.extent[1],
                self.center[2] + self.extent[2]
            ],
        ]


def create_rectangle(bounds):
    return Rectangle(bounds)
