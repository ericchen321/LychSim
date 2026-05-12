import numpy as np
from scipy.spatial.transform import Rotation as R


def get_bbox3d(center, extent):
    """Get 3D bounding box corners and edges.

    Args:
        center (np.ndarray): Center of the bounding box (3,).
        extent (np.ndarray): Extent of the bounding box (3,).

    Returns:
        corners (np.ndarray): 3D bounding box corners (8, 3).
        edges (np.ndarray): 3D bounding box edges (12, 2).
    """
    corners = np.array(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [1, 1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
            [1, -1, 1],
            [1, 1, 1],
            [-1, 1, 1],
        ]
    )
    edges = np.array(
        [
            [0, 1],
            [1, 2],
            [2, 3],
            [3, 0],
            [4, 5],
            [5, 6],
            [6, 7],
            [7, 4],
            [0, 4],
            [1, 5],
            [2, 6],
            [3, 7],
        ]
    )
    corners = corners * extent
    corners = corners + center
    return corners, edges


def fx_fy_from_fovx(fovx_deg, W, H):
    fovx = np.deg2rad(fovx_deg)
    fx = 0.5 * W / np.tan(0.5 * fovx)
    fovy = 2.0 * np.arctan((H / float(W)) * np.tan(0.5 * fovx))
    fy = 0.5 * H / np.tan(0.5 * fovy)
    return fx, fy


def project_3d_to_2d(corners, c2w, fov, W, H):
    """Project 3D points to 2D image plane.

    Args:
        corners (np.ndarray): 3D points (N, 3).
        c2w (np.ndarray): Camera-to-world transformation matrix (4, 4).
        fov (float): Horizontal field of view in degrees.
        W (int): Image width.
        H (int): Image height.

    Returns:
        uv (np.ndarray): 2D projected points (N, 2).
        in_front (np.ndarray): Boolean mask indicating if points are in front of the camera (N,).
    """
    w2c = np.linalg.inv(c2w)
    pts_h = np.concatenate([corners, np.ones((corners.shape[0], 1))], axis=1)
    pc = (w2c @ pts_h.T).T
    Xc, Yc, Zc = pc[:, 0], pc[:, 1], pc[:, 2]

    in_front = Xc > 0

    fx, fy = fx_fy_from_fovx(fov, W, H)
    cx, cy = 0.5 * W, 0.5 * H

    u = fx * (Yc / Xc) + cx
    v = fy * (-Zc / Xc) + cy

    uv = np.stack([u, v], axis=-1).reshape(-1, 2)
    in_front = in_front.reshape(corners.shape[:-1])
    return uv, in_front


def rot_mat(rotation):
    """Convert rotation from (XZY) Euler angles in degrees to rotation matrix.

    Args:
        rotation (list or np.ndarray): Rotation angles in degrees [rx, ry, rz].

    Returns:
        np.ndarray: Rotation matrix (3, 3).
    """
    r = R.from_euler("XZY", rotation, degrees=True)
    return r.as_matrix()
