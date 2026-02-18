"""Geospatial-aware data augmentations.

All augmentations operate on NumPy arrays and preserve geospatial
semantics (e.g. no interpolation artefacts that break spectral fidelity).
Designed for satellite and remote-sensing imagery where the channel
dimension is first: ``(C, H, W)``.
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np


class RandomRotation90:
    """Randomly rotate an image by a multiple of 90 degrees.

    Works on ``(C, H, W)`` arrays.  The same rotation is applied to both
    image and label if a label is provided.
    """

    def __call__(
        self, image: np.ndarray, label: np.ndarray | None = None
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        k = np.random.randint(0, 4)  # 0, 90, 180, 270
        image = np.rot90(image, k, axes=(1, 2)).copy()
        if label is not None:
            label = np.rot90(label, k, axes=(0, 1)).copy()
            return image, label
        return image


class RandomFlip:
    """Random horizontal and/or vertical flip.

    Args:
        horizontal: Enable horizontal flipping.
        vertical: Enable vertical flipping.
        p: Independent probability of each flip.
    """

    def __init__(
        self,
        horizontal: bool = True,
        vertical: bool = True,
        p: float = 0.5,
    ) -> None:
        self.horizontal = horizontal
        self.vertical = vertical
        self.p = p

    def __call__(
        self, image: np.ndarray, label: np.ndarray | None = None
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        if self.horizontal and np.random.random() < self.p:
            image = np.flip(image, axis=2).copy()
            if label is not None:
                label = np.flip(label, axis=1).copy()

        if self.vertical and np.random.random() < self.p:
            image = np.flip(image, axis=1).copy()
            if label is not None:
                label = np.flip(label, axis=0).copy()

        if label is not None:
            return image, label
        return image


class SpectralJitter:
    """Random per-band intensity scaling for spectral augmentation.

    Each band is independently scaled by a factor drawn from
    ``U(1 - magnitude, 1 + magnitude)``.

    Args:
        magnitude: Maximum scaling deviation from 1.0.
    """

    def __init__(self, magnitude: float = 0.1) -> None:
        self.magnitude = magnitude

    def __call__(
        self, image: np.ndarray, label: np.ndarray | None = None
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        n_bands = image.shape[0]
        scales = np.random.uniform(
            1.0 - self.magnitude,
            1.0 + self.magnitude,
            size=(n_bands, 1, 1),
        ).astype(image.dtype)
        image = (image * scales).copy()

        if label is not None:
            return image, label
        return image


class GaussianNoise:
    """Additive Gaussian noise.

    Args:
        mean: Mean of the Gaussian distribution.
        std: Standard deviation.
    """

    def __init__(self, mean: float = 0.0, std: float = 0.01) -> None:
        self.mean = mean
        self.std = std

    def __call__(
        self, image: np.ndarray, label: np.ndarray | None = None
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        noise = np.random.normal(self.mean, self.std, image.shape).astype(image.dtype)
        image = (image + noise).copy()

        if label is not None:
            return image, label
        return image


class Compose:
    """Compose multiple augmentations sequentially.

    All augmentations in the pipeline must accept and return either a
    single ``image`` array or a ``(image, label)`` tuple.

    Args:
        transforms: Ordered sequence of augmentation callables.
    """

    def __init__(self, transforms: Sequence[Any]) -> None:
        self.transforms = list(transforms)

    def __call__(
        self, image: np.ndarray, label: np.ndarray | None = None
    ) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
        for t in self.transforms:
            result = t(image, label)
            if isinstance(result, tuple):
                image, label = result
            else:
                image = result
        if label is not None:
            return image, label
        return image

    def __repr__(self) -> str:
        names = [type(t).__name__ for t in self.transforms]
        return f"Compose([{', '.join(names)}])"


__all__ = [
    "Compose",
    "GaussianNoise",
    "RandomFlip",
    "RandomRotation90",
    "SpectralJitter",
]
