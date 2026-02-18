"""Raster data processor for COG/GeoTIFF processing."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from ecotrack.logging import get_logger

from .base import DataProcessor

logger = get_logger(__name__)


@dataclass
class RasterData:
    """Container for raster data with spatial metadata.

    Attributes:
        array: The raster pixel values as a numpy array (bands × height × width).
        transform: Affine transform mapping pixel to geographic coordinates.
        crs: Coordinate reference system string (e.g. ``"EPSG:4326"``).
        nodata: No-data sentinel value.
        bounds: Geographic bounds ``(left, bottom, right, top)``.
        metadata: Arbitrary key/value metadata.
    """

    array: np.ndarray
    transform: Any  # rasterio Affine
    crs: str = "EPSG:4326"
    nodata: float | None = None
    bounds: tuple[float, float, float, float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RasterStatistics:
    """Summary statistics computed from a raster.

    Attributes:
        min: Minimum pixel value (excluding nodata).
        max: Maximum pixel value.
        mean: Mean pixel value.
        std: Standard deviation.
        median: Median pixel value.
        count: Number of valid pixels.
        nodata_count: Number of nodata pixels.
        histogram: Optional histogram ``(counts, bin_edges)``.
    """

    min: float
    max: float
    mean: float
    std: float
    median: float
    count: int
    nodata_count: int
    histogram: tuple[np.ndarray, np.ndarray] | None = None


class RasterProcessor(DataProcessor[RasterData, RasterData]):
    """Processor for Cloud-Optimised GeoTIFF and raster data.

    Provides reprojection, resampling, NDVI computation, spatial
    clipping, and summary statistics.  Uses ``rasterio`` for I/O
    and ``numpy`` for computation.
    """

    # ------------------------------------------------------------------
    # DataProcessor interface
    # ------------------------------------------------------------------

    async def process(self, data: RasterData) -> RasterData:
        """Default processing: mask nodata values.

        Override or compose with specific methods for custom pipelines.

        Args:
            data: Input raster data.

        Returns:
            Raster with nodata values replaced by ``np.nan``.
        """
        masked = self._mask_nodata(data)
        return masked

    async def validate_input(self, data: RasterData) -> bool:
        """Validate input raster data.

        Checks:
        - ``array`` is a numpy array with 2 or 3 dimensions.
        - ``crs`` is a non-empty string.
        - ``transform`` is not None.

        Args:
            data: Raster data to validate.

        Returns:
            ``True`` if valid.
        """
        if not isinstance(data.array, np.ndarray):
            logger.warning("raster.validate_input: array is not ndarray")
            return False
        if data.array.ndim not in (2, 3):
            logger.warning("raster.validate_input: array ndim=%d", data.array.ndim)
            return False
        if not data.crs:
            logger.warning("raster.validate_input: missing CRS")
            return False
        if data.transform is None:
            logger.warning("raster.validate_input: missing transform")
            return False
        return True

    async def validate_output(self, data: RasterData) -> bool:
        """Validate output raster data.

        Same checks as input validation.

        Args:
            data: Processed raster data.

        Returns:
            ``True`` if valid.
        """
        return await self.validate_input(data)

    # ------------------------------------------------------------------
    # Raster operations
    # ------------------------------------------------------------------

    async def reproject(
        self,
        data: RasterData,
        target_crs: str = "EPSG:4326",
    ) -> RasterData:
        """Reproject raster to a different CRS.

        Uses ``rasterio.warp.reproject`` for the transformation.

        Args:
            data: Source raster data.
            target_crs: Target CRS string (default ``"EPSG:4326"``).

        Returns:
            Reprojected :class:`RasterData`.
        """
        import rasterio
        from rasterio.crs import CRS
        from rasterio.warp import Resampling, calculate_default_transform, reproject

        src_crs = CRS.from_string(data.crs)
        dst_crs = CRS.from_string(target_crs)

        if src_crs == dst_crs:
            return data

        arr = data.array
        if arr.ndim == 2:
            arr = arr[np.newaxis, :, :]

        bands, height, width = arr.shape

        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            dst_crs,
            width,
            height,
            *data.bounds if data.bounds else (0, 0, width, height),
        )

        dst_array = np.empty((bands, dst_height, dst_width), dtype=arr.dtype)
        for band_idx in range(bands):
            reproject(
                source=arr[band_idx],
                destination=dst_array[band_idx],
                src_transform=data.transform,
                src_crs=src_crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.bilinear,
                src_nodata=data.nodata,
            )

        logger.info(
            "raster.reproject",
            src_crs=str(src_crs),
            dst_crs=str(dst_crs),
            shape=dst_array.shape,
        )
        return RasterData(
            array=dst_array.squeeze() if bands == 1 else dst_array,
            transform=dst_transform,
            crs=target_crs,
            nodata=data.nodata,
            bounds=None,  # Recalculate from new transform if needed
            metadata={**data.metadata, "reprojected_from": data.crs},
        )

    async def resample(
        self,
        data: RasterData,
        scale_factor: float = 0.5,
    ) -> RasterData:
        """Resample raster to a different resolution.

        Args:
            data: Source raster.
            scale_factor: Factor < 1.0 = downsample, > 1.0 = upsample.

        Returns:
            Resampled :class:`RasterData`.
        """
        from scipy.ndimage import zoom

        arr = data.array
        if arr.ndim == 2:
            resampled = zoom(arr, scale_factor, order=1)
        else:
            # Zoom spatial dimensions only
            zoom_factors = [1] + [scale_factor] * (arr.ndim - 1)
            resampled = zoom(arr, zoom_factors, order=1)

        logger.info(
            "raster.resample",
            original_shape=arr.shape,
            new_shape=resampled.shape,
            scale_factor=scale_factor,
        )
        return RasterData(
            array=resampled,
            transform=data.transform,  # Would need rescaling for production
            crs=data.crs,
            nodata=data.nodata,
            metadata={**data.metadata, "resampled_scale": scale_factor},
        )

    async def compute_ndvi(self, data: RasterData) -> RasterData:
        """Compute NDVI from a multi-band raster.

        Expects the raster to contain NIR (band index 3 for Sentinel-2)
        and Red (band index 2) bands.  Band indices are 0-based.

        NDVI = (NIR − Red) / (NIR + Red)

        Args:
            data: Multi-band raster with at least 4 bands.

        Returns:
            Single-band :class:`RasterData` with NDVI values in [-1, 1].

        Raises:
            ValueError: If the raster has fewer than 4 bands.
        """
        arr = data.array
        if arr.ndim != 3 or arr.shape[0] < 4:
            raise ValueError(
                f"NDVI requires at least 4 bands, got shape {arr.shape}"
            )

        nir = arr[3].astype(np.float64)
        red = arr[2].astype(np.float64)

        denominator = nir + red
        ndvi = np.where(denominator != 0, (nir - red) / denominator, 0.0)
        ndvi = np.clip(ndvi, -1.0, 1.0)

        logger.info("raster.compute_ndvi", shape=ndvi.shape)
        return RasterData(
            array=ndvi,
            transform=data.transform,
            crs=data.crs,
            nodata=np.nan,
            bounds=data.bounds,
            metadata={**data.metadata, "derived": "ndvi"},
        )

    async def clip_to_bbox(
        self,
        data: RasterData,
        bbox: tuple[float, float, float, float],
    ) -> RasterData:
        """Clip raster to a bounding box.

        Uses ``rasterio.mask.mask`` for efficient spatial subsetting.

        Args:
            data: Source raster.
            bbox: ``(min_lon, min_lat, max_lon, max_lat)``.

        Returns:
            Clipped :class:`RasterData`.
        """
        from rasterio.features import geometry_mask
        from shapely.geometry import box

        geom = box(*bbox)
        arr = data.array
        if arr.ndim == 2:
            arr = arr[np.newaxis, :, :]

        _, height, width = arr.shape

        # Create a mask from the geometry
        mask = geometry_mask(
            [geom],
            out_shape=(height, width),
            transform=data.transform,
            invert=True,
        )

        clipped = arr.copy()
        for band_idx in range(clipped.shape[0]):
            clipped[band_idx][~mask] = data.nodata if data.nodata is not None else 0

        logger.info("raster.clip_to_bbox", bbox=bbox)
        return RasterData(
            array=clipped.squeeze() if clipped.shape[0] == 1 else clipped,
            transform=data.transform,
            crs=data.crs,
            nodata=data.nodata,
            bounds=bbox,
            metadata={**data.metadata, "clipped_bbox": bbox},
        )

    async def compute_statistics(self, data: RasterData) -> RasterStatistics:
        """Compute summary statistics for a raster.

        Nodata values are excluded from all calculations.

        Args:
            data: Input raster data.

        Returns:
            :class:`RasterStatistics` with computed values.
        """
        arr = data.array.astype(np.float64)

        if data.nodata is not None:
            valid_mask = arr != data.nodata
        else:
            valid_mask = ~np.isnan(arr)

        valid = arr[valid_mask]
        nodata_count = int(np.sum(~valid_mask))

        if valid.size == 0:
            return RasterStatistics(
                min=0.0,
                max=0.0,
                mean=0.0,
                std=0.0,
                median=0.0,
                count=0,
                nodata_count=nodata_count,
            )

        hist_counts, hist_edges = np.histogram(valid, bins=50)

        stats = RasterStatistics(
            min=float(np.min(valid)),
            max=float(np.max(valid)),
            mean=float(np.mean(valid)),
            std=float(np.std(valid)),
            median=float(np.median(valid)),
            count=int(valid.size),
            nodata_count=nodata_count,
            histogram=(hist_counts, hist_edges),
        )

        logger.info(
            "raster.statistics",
            min=stats.min,
            max=stats.max,
            mean=stats.mean,
            count=stats.count,
        )
        return stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mask_nodata(data: RasterData) -> RasterData:
        """Replace nodata values with ``np.nan``.

        Args:
            data: Source raster.

        Returns:
            New :class:`RasterData` with nodata → NaN.
        """
        arr = data.array.astype(np.float64)
        if data.nodata is not None:
            arr[arr == data.nodata] = np.nan
        return RasterData(
            array=arr,
            transform=data.transform,
            crs=data.crs,
            nodata=np.nan,
            bounds=data.bounds,
            metadata=data.metadata,
        )

    @staticmethod
    async def read_geotiff(path: Path) -> RasterData:
        """Read a GeoTIFF file into a :class:`RasterData` container.

        Args:
            path: Path to the GeoTIFF file.

        Returns:
            :class:`RasterData` with loaded array and spatial metadata.
        """
        import rasterio

        with rasterio.open(path) as src:
            arr = src.read()
            return RasterData(
                array=arr.squeeze() if arr.shape[0] == 1 else arr,
                transform=src.transform,
                crs=str(src.crs),
                nodata=src.nodata,
                bounds=src.bounds,
                metadata=dict(src.tags()),
            )

    @staticmethod
    async def write_geotiff(
        data: RasterData,
        path: Path,
        *,
        compress: str = "deflate",
    ) -> Path:
        """Write raster data to a GeoTIFF file.

        Args:
            data: Raster data to write.
            path: Destination file path.
            compress: Compression algorithm.

        Returns:
            The output file path.
        """
        import rasterio
        from rasterio.crs import CRS

        arr = data.array
        if arr.ndim == 2:
            arr = arr[np.newaxis, :, :]

        bands, height, width = arr.shape
        path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=height,
            width=width,
            count=bands,
            dtype=arr.dtype,
            crs=CRS.from_string(data.crs),
            transform=data.transform,
            nodata=data.nodata,
            compress=compress,
        ) as dst:
            dst.write(arr)

        logger.info("raster.write_geotiff", path=str(path), shape=arr.shape)
        return path


__all__ = ["RasterProcessor", "RasterData", "RasterStatistics"]
