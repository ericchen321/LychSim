import base64
from itertools import groupby
from typing import Any, Dict

import numpy as np
from pycocotools import mask
from shapely import Polygon

__all__ = ["polygon_to_dict", "polygon_from_dict"]


def polygon_to_dict(polygon: Polygon) -> dict:
    return dict(
        exterior=np.array(polygon.exterior.coords),
        holes=[np.array(hole.coords) for hole in polygon.interiors],
    )


def polygon_from_dict(data_dict: Dict[str, Any]) -> Polygon:
    return Polygon(data_dict["exterior"], [hole for hole in data_dict["holes"]])


def mask_to_rle(binary_mask: np.ndarray) -> Dict[str, Any] | list[Dict[str, Any]]:
    if binary_mask.ndim == 2:
        binary_mask = binary_mask[np.newaxis, :, :]
        unpack = True
    all_rles = []
    for i in range(binary_mask.shape[0]):
        rle = {"counts": [], "size": list(binary_mask[i].shape)}
        counts = rle.get("counts")
        for i, (value, elements) in enumerate(groupby(binary_mask[i].ravel(order="F"))):
            if i == 0 and value == 1:
                counts.append(0)
            counts.append(len(list(elements)))
        compressed_rle = mask.frPyObjects(rle, rle.get("size")[0], rle.get("size")[1])
        compressed_rle["counts"] = base64.b64encode(compressed_rle["counts"]).decode(
            "ascii"
        )
        all_rles.append(compressed_rle)
    if unpack:
        return all_rles[0]
    return all_rles


def rle_to_mask(compressed_rles: Dict[str, Any] | list[Dict[str, Any]]) -> np.ndarray:
    def _rle_to_mask(rle):
        rle["counts"] = base64.b64decode(rle["counts"])
        return mask.decode(rle).astype(bool)

    if isinstance(compressed_rles, list):
        masks = [_rle_to_mask(rle) for rle in compressed_rles]
        return np.stack(masks, axis=0)
    else:
        return _rle_to_mask(compressed_rles)
