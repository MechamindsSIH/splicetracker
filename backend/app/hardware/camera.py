"""Camera providers and frame buffer for the SpliceTracker vision subsystem.

Includes an abstract base, a simulation provider that generates synthetic
conveyor-belt frames with injectable defects, a real USB webcam provider,
and a ring-buffer that can capture event windows.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Tuple

import numpy as np

try:
    import cv2

    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _CV2_AVAILABLE = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class CameraProvider(ABC):
    """Abstract camera interface."""

    @abstractmethod
    async def start(self) -> None:
        """Open the camera and begin frame acquisition."""

    @abstractmethod
    async def stop(self) -> None:
        """Release camera resources."""

    @abstractmethod
    async def get_frame(self) -> Tuple[np.ndarray, float]:
        """Return the latest frame and its UNIX timestamp.

        Returns:
            A tuple of (frame_array, timestamp).
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` when the camera is ready to provide frames."""


# ---------------------------------------------------------------------------
# Simulation provider
# ---------------------------------------------------------------------------


class SimulationCameraProvider(CameraProvider):
    """Generates synthetic conveyor-belt frames with optional defects.

    The simulated image consists of:
      * A gray belt background with Gaussian noise.
      * A horizontal splice region band across the vertical centre.
      * Optional anomalies injected into the splice region.
    """

    ANOMALY_MODES = {"crack", "deformation", "discoloration", "edge_damage"}

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.running = False
        self._frame_count = 0

        # Anomaly injection state
        self.anomaly_mode: Optional[str] = None
        self.anomaly_intensity: float = 0.5

        # Internal RNG for reproducibility within a session
        self._rng = np.random.default_rng()

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        self.running = True
        self._frame_count = 0
        logger.info("SimulationCameraProvider started (%dx%d @ %d fps)", self.width, self.height, self.fps)

    async def stop(self) -> None:
        self.running = False
        logger.info("SimulationCameraProvider stopped")

    def is_connected(self) -> bool:
        return self.running

    # -- anomaly control -----------------------------------------------------

    def set_anomaly(self, mode: Optional[str], intensity: float = 0.5) -> None:
        """Configure the anomaly to inject into subsequent frames.

        Args:
            mode: One of ``'crack'``, ``'deformation'``, ``'discoloration'``,
                  ``'edge_damage'``, or ``None`` to clear.
            intensity: Anomaly strength in ``[0, 1]``.
        """
        if mode is not None and mode not in self.ANOMALY_MODES:
            raise ValueError(f"Unknown anomaly mode '{mode}'. Choose from {self.ANOMALY_MODES}")
        self.anomaly_mode = mode
        self.anomaly_intensity = float(np.clip(intensity, 0.0, 1.0))

    # -- frame generation ----------------------------------------------------

    async def get_frame(self) -> Tuple[np.ndarray, float]:
        if not self.running:
            raise RuntimeError("Camera is not started")

        # Throttle to target FPS
        await asyncio.sleep(1.0 / self.fps)

        timestamp = time.time()
        frame = self._generate_frame()
        self._frame_count += 1
        return frame, timestamp

    def _generate_frame(self) -> np.ndarray:
        """Build a single synthetic BGR frame."""
        rng = self._rng
        h, w = self.height, self.width

        # -- base belt texture (gray ~128 with Gaussian noise) ---------------
        base_value = 128
        noise = rng.normal(0, 8, size=(h, w)).astype(np.float32)
        gray = np.full((h, w), base_value, dtype=np.float32) + noise

        # -- splice region band (slightly brighter, centred vertically) ------
        splice_top = int(h * 0.42)
        splice_bot = int(h * 0.58)
        gray[splice_top:splice_bot, :] += 15  # splice is lighter

        # Add subtle horizontal texture lines in splice region
        for row_offset in range(0, splice_bot - splice_top, 4):
            row = splice_top + row_offset
            if row < splice_bot:
                gray[row, :] += rng.normal(0, 3, size=w).astype(np.float32)

        # Clamp and convert to uint8 BGR
        gray = np.clip(gray, 0, 255).astype(np.uint8)
        frame = np.stack([gray, gray, gray], axis=-1)  # BGR

        # -- inject anomaly if configured ------------------------------------
        if self.anomaly_mode is not None:
            frame = self._inject_anomaly(frame, splice_top, splice_bot)

        return frame

    def _inject_anomaly(self, frame: np.ndarray, splice_top: int, splice_bot: int) -> np.ndarray:
        """Draw the configured anomaly into the splice region of *frame* (mutated in-place)."""
        mode = self.anomaly_mode
        intensity = self.anomaly_intensity
        rng = self._rng
        h, w = self.height, self.width
        splice_h = splice_bot - splice_top
        splice_cy = (splice_top + splice_bot) // 2

        if mode == "crack":
            # Dark diagonal lines across the splice region
            num_cracks = max(1, int(3 * intensity))
            for _ in range(num_cracks):
                x_start = int(rng.integers(w // 4, 3 * w // 4))
                y_start = int(rng.integers(splice_top, splice_cy))
                length = int(rng.integers(40, 120) * intensity)
                angle = rng.uniform(-0.7, 0.7)  # near-vertical crack
                x_end = x_start + int(length * np.sin(angle))
                y_end = y_start + int(length * np.cos(angle))
                thickness = max(1, int(2 * intensity))
                darkness = int(60 + 80 * intensity)
                if _CV2_AVAILABLE:
                    cv2.line(frame, (x_start, y_start), (x_end, y_end), (base := 128 - darkness, base, base), thickness)
                else:
                    # Fallback: draw crack with numpy (Bresenham-like)
                    self._draw_line_np(frame, x_start, y_start, x_end, y_end, darkness, thickness)

        elif mode == "deformation":
            # Bright bulging region with radial gradient
            cx = int(rng.integers(w // 3, 2 * w // 3))
            cy = splice_cy
            radius = int(30 + 50 * intensity)
            yy, xx = np.ogrid[:h, :w]
            dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(np.float32)
            mask = dist < radius
            brightness_boost = (1.0 - dist / radius) * 80 * intensity
            brightness_boost = np.clip(brightness_boost, 0, 255)
            for c in range(3):
                channel = frame[:, :, c].astype(np.float32)
                channel[mask] += brightness_boost[mask]
                frame[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

        elif mode == "discoloration":
            # Colour shift in a rectangular patch (warm tint)
            patch_w = int(80 + 100 * intensity)
            patch_h = int(splice_h * 0.6)
            px = int(rng.integers(w // 4, 3 * w // 4 - patch_w))
            py = splice_top + (splice_h - patch_h) // 2
            region = frame[py : py + patch_h, px : px + patch_w].astype(np.float32)
            # Add warm discolouration: boost red, reduce blue
            region[:, :, 2] += 40 * intensity  # R
            region[:, :, 0] -= 25 * intensity  # B
            frame[py : py + patch_h, px : px + patch_w] = np.clip(region, 0, 255).astype(np.uint8)

        elif mode == "edge_damage":
            # Irregular dark blotches along the top and bottom edges of the splice
            num_spots = max(2, int(6 * intensity))
            for _ in range(num_spots):
                ex = int(rng.integers(0, w))
                edge_row = int(rng.choice([splice_top, splice_bot - 1]))
                spot_radius = int(5 + 15 * intensity)
                yy, xx = np.ogrid[:h, :w]
                dist = np.sqrt((xx - ex) ** 2 + (yy - edge_row) ** 2).astype(np.float32)
                spot_mask = dist < spot_radius
                darkening = (1.0 - dist / spot_radius) * 90 * intensity
                darkening = np.clip(darkening, 0, 255)
                for c in range(3):
                    channel = frame[:, :, c].astype(np.float32)
                    channel[spot_mask] -= darkening[spot_mask]
                    frame[:, :, c] = np.clip(channel, 0, 255).astype(np.uint8)

        return frame

    # -- numpy-only line drawing fallback ------------------------------------

    @staticmethod
    def _draw_line_np(
        frame: np.ndarray,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        darkness: int,
        thickness: int,
    ) -> None:
        """Draw a dark anti-aliased line using numpy when cv2 is unavailable."""
        h, w = frame.shape[:2]
        num_pts = max(abs(x1 - x0), abs(y1 - y0), 1) * 2
        xs = np.linspace(x0, x1, num_pts).astype(int)
        ys = np.linspace(y0, y1, num_pts).astype(int)
        half = max(thickness // 2, 1)
        for px, py in zip(xs, ys):
            r_start = max(0, py - half)
            r_end = min(h, py + half + 1)
            c_start = max(0, px - half)
            c_end = min(w, px + half + 1)
            frame[r_start:r_end, c_start:c_end] = np.clip(
                frame[r_start:r_end, c_start:c_end].astype(np.int16) - darkness,
                0,
                255,
            ).astype(np.uint8)


# ---------------------------------------------------------------------------
# Real USB webcam provider
# ---------------------------------------------------------------------------


class USBWebcamProvider(CameraProvider):
    """Wraps ``cv2.VideoCapture`` for a USB or built-in webcam."""

    def __init__(
        self,
        camera_index: int = 0,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
    ) -> None:
        if not _CV2_AVAILABLE:
            raise ImportError("OpenCV (cv2) is required for USBWebcamProvider")
        self._camera_index = camera_index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: Any = None
        self._connected = False

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._open_camera)

    def _open_camera(self) -> None:
        self._cap = cv2.VideoCapture(self._camera_index)
        if not self._cap.isOpened():
            logger.error("Failed to open camera at index %d", self._camera_index)
            self._connected = False
            return
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)
        self._connected = True
        logger.info(
            "USBWebcamProvider started (index=%d, %dx%d @ %d fps)",
            self._camera_index,
            self._width,
            self._height,
            self._fps,
        )

    async def stop(self) -> None:
        if self._cap is not None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._release_camera)
        self._connected = False
        logger.info("USBWebcamProvider stopped")

    def _release_camera(self) -> None:
        try:
            self._cap.release()
        except Exception:
            logger.exception("Error releasing camera")
        finally:
            self._cap = None

    def is_connected(self) -> bool:
        return self._connected and self._cap is not None and self._cap.isOpened()

    async def get_frame(self) -> Tuple[np.ndarray, float]:
        if not self.is_connected():
            raise RuntimeError("Camera is not connected")
        loop = asyncio.get_running_loop()
        frame = await loop.run_in_executor(None, self._read_frame)
        timestamp = time.time()
        return frame, timestamp

    def _read_frame(self) -> np.ndarray:
        ret, frame = self._cap.read()
        if not ret or frame is None:
            self._connected = False
            raise RuntimeError("Failed to read frame from camera")
        return frame


# ---------------------------------------------------------------------------
# Frame ring buffer with event capture
# ---------------------------------------------------------------------------


class FrameBuffer:
    """Thread-safe ring buffer that stores recent frames and can snapshot
    windows around events.

    Args:
        maxlen: Maximum number of frames to retain.
        pre_event_count: Frames to keep *before* an event trigger.
        post_event_count: Frames to keep *after* an event trigger.
    """

    def __init__(
        self,
        maxlen: int = 100,
        pre_event_count: int = 10,
        post_event_count: int = 10,
    ) -> None:
        self._buffer: deque[Tuple[np.ndarray, float]] = deque(maxlen=maxlen)
        self._pre_event_count = pre_event_count
        self._post_event_count = post_event_count
        self._lock = asyncio.Lock()
        # Pending event captures: event_id -> {"pre": [...], "remaining_post": int, "post": [...]}
        self._pending_captures: dict[str, dict] = {}
        self._completed_captures: dict[str, List[Tuple[np.ndarray, float]]] = {}

    def add_frame(self, frame: np.ndarray, timestamp: float) -> None:
        """Add a frame to the ring buffer (copies the array)."""
        entry = (frame.copy(), timestamp)
        self._buffer.append(entry)

        # Accumulate post-event frames for any pending captures
        finished = []
        for event_id, capture in self._pending_captures.items():
            if capture["remaining_post"] > 0:
                capture["post"].append(entry)
                capture["remaining_post"] -= 1
            if capture["remaining_post"] <= 0:
                finished.append(event_id)

        for event_id in finished:
            capture = self._pending_captures.pop(event_id)
            self._completed_captures[event_id] = capture["pre"] + capture["post"]

    def trigger_event_capture(self, event_id: str) -> None:
        """Begin capturing a window of frames around the current moment.

        Pre-event frames are taken from the existing buffer.  Post-event
        frames are collected as subsequent frames arrive via :meth:`add_frame`.
        """
        pre_frames = list(self._buffer)[-self._pre_event_count :]
        self._pending_captures[event_id] = {
            "pre": list(pre_frames),
            "remaining_post": self._post_event_count,
            "post": [],
        }
        logger.debug(
            "Event capture triggered: %s (pre=%d frames buffered)",
            event_id,
            len(pre_frames),
        )

    def get_recent_frames(self, count: int) -> List[Tuple[np.ndarray, float]]:
        """Return the last *count* ``(frame, timestamp)`` pairs."""
        return list(self._buffer)[-count:]

    async def save_event_frames(
        self,
        event_id: str,
        output_dir: str,
    ) -> List[str]:
        """Save the captured event frames as PNG files.

        If the capture is still pending, waits briefly for remaining
        post-event frames before saving whatever is available.

        Returns:
            List of absolute file paths of saved images.
        """
        if not _CV2_AVAILABLE:
            logger.warning("cv2 not available; cannot save event frames")
            return []

        # Wait up to 5 seconds for post-event frames to accumulate
        for _ in range(50):
            if event_id in self._completed_captures:
                break
            if event_id in self._pending_captures:
                await asyncio.sleep(0.1)
            else:
                break

        # Gather frames: completed, pending, or fallback to recent
        if event_id in self._completed_captures:
            frames = self._completed_captures.pop(event_id)
        elif event_id in self._pending_captures:
            capture = self._pending_captures.pop(event_id)
            frames = capture["pre"] + capture["post"]
        else:
            frames = self.get_recent_frames(self._pre_event_count)

        if not frames:
            return []

        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        saved_paths: List[str] = []
        loop = asyncio.get_running_loop()
        for idx, (frame, ts) in enumerate(frames):
            fname = f"{event_id}_frame_{idx:04d}_{ts:.3f}.png"
            fpath = str(out / fname)
            # cv2.imwrite is blocking; offload to executor
            success = await loop.run_in_executor(None, cv2.imwrite, fpath, frame)
            if success:
                saved_paths.append(os.path.abspath(fpath))
            else:
                logger.warning("Failed to write frame: %s", fpath)

        logger.info("Saved %d event frames for %s", len(saved_paths), event_id)
        return saved_paths
