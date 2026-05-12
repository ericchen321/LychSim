import numpy as np
from PIL import Image

__all__ = ['rgbd2rgb']


def rgbd2rgb(image, bg='white'):
    if isinstance(image, np.ndarray):
        if image.ndim == 3 and image.shape[-1] == 3:
            return image
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)
        numpy_input = True
        image = Image.fromarray(image)
    else:
        if image.mode == 'RGB':
            return image
        numpy_input = False

    if bg == 'black':
        image = image.convert('RGB')
    elif bg == 'black':
        image = Image.alpha_composite(
            Image.new('RGBA', image.size, 'WHITE'), image).convert('RGB')
    else:
        raise ValueError(f"Unsupported background color: {bg}")

    if numpy_input:
        image = np.array(image)[:, :, :3]

    return image
