"""Unified hardware manager for the SpliceTracker system.

Instantiates the appropriate provider (simulation or real) for each sensor
based on the application :class:`Settings`, and exposes a single interface
for reading all sensors, querying status, and injecting test anomalies.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional

import numpy as np

from .camera import (
    CameraProvider,
    FrameBuffer,
    SimulationCameraProvider,
    USBWebcamProvider,
)
from .thermal import (
    ThermalProvider,
    SimulationThermalProvider,
    RealThermalProvider,
)
from .conductive import (
    ConductiveProvider,
    SimulationConductiveProvider,
    RealConductiveProvider,
)
from .mechanical import (
    MechanicalProvider,
    SimulationMechanicalProvider,
    RealMechanicalProvider,
)
from .belt_position import (
    BeltPositionProvider,
    SimulationBeltPositionProvider,
    EncoderBeltPositionProvider,
)

logger = logging.getLogger(__name__)


class HardwareManager:
    """Central façade for all hardware providers.

    Args:
        config: A :class:`Settings` instance (from ``app.config``).
    """

    def __init__(self, config: Any) -> None:
        self._config = config

        # Provider slots (populated in ``initialize``)
        self.camera: Optional[CameraProvider] = None
        self.thermal: Optional[ThermalProvider] = None
        self.conductive: Optional[ConductiveProvider] = None
        self.mechanical: Optional[MechanicalProvider] = None
        self.belt_position: Optional[BeltPositionProvider] = None
        self.frame_buffer: Optional[FrameBuffer] = None

        self._initialized = False

    # -- lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Create and start all hardware providers according to config."""
        cfg = self._config
        simulation = cfg.SIMULATION_MODE

        logger.info("Initialising hardware (simulation=%s)", simulation)

        # Camera
        if simulation:
            cam = SimulationCameraProvider(
                width=cfg.CAMERA_WIDTH,
                height=cfg.CAMERA_HEIGHT,
                fps=cfg.CAMERA_FPS,
            )
        else:
            cam = USBWebcamProvider(
                camera_index=cfg.CAMERA_INDEX,
                width=cfg.CAMERA_WIDTH,
                height=cfg.CAMERA_HEIGHT,
                fps=cfg.CAMERA_FPS,
            )
        await cam.start()
        self.camera = cam

        # Frame buffer
        self.frame_buffer = FrameBuffer(
            maxlen=cfg.FRAME_BUFFER_SIZE,
            pre_event_count=max(cfg.FRAME_BUFFER_SIZE // 10, 5),
            post_event_count=max(cfg.FRAME_BUFFER_SIZE // 10, 5),
        )

        # Thermal
        if cfg.THERMAL_ENABLED:
            if simulation:
                self.thermal = SimulationThermalProvider()
            else:
                provider = RealThermalProvider()
                await provider.start()
                self.thermal = provider
        else:
            logger.info("Thermal sensor disabled by configuration")

        # Conductive
        if cfg.CONDUCTIVE_ENABLED:
            if simulation:
                self.conductive = SimulationConductiveProvider()
            else:
                provider = RealConductiveProvider()
                await provider.start()
                self.conductive = provider
        else:
            logger.info("Conductive sensor disabled by configuration")

        # Mechanical
        if cfg.MECHANICAL_ENABLED:
            if simulation:
                self.mechanical = SimulationMechanicalProvider()
            else:
                provider = RealMechanicalProvider()
                await provider.start()
                self.mechanical = provider
        else:
            logger.info("Mechanical sensor disabled by configuration")

        # Belt position
        if simulation:
            bp = SimulationBeltPositionProvider(
                belt_speed=cfg.BELT_SPEED,
                belt_length=cfg.BELT_LENGTH,
            )
        else:
            bp = EncoderBeltPositionProvider()
            await bp.start()
        await bp.start() if simulation else None
        self.belt_position = bp

        self._initialized = True
        logger.info("Hardware initialisation complete")

    async def shutdown(self) -> None:
        """Gracefully stop all providers and release resources."""
        logger.info("Shutting down hardware providers")
        errors = []

        if self.camera is not None:
            try:
                await self.camera.stop()
            except Exception as exc:
                errors.append(("camera", exc))

        if self.belt_position is not None:
            try:
                await self.belt_position.stop()
            except Exception as exc:
                errors.append(("belt_position", exc))

        # Thermal, conductive, mechanical may have stop() if they are real providers
        for name, provider in [
            ("thermal", self.thermal),
            ("conductive", self.conductive),
            ("mechanical", self.mechanical),
        ]:
            if provider is not None and hasattr(provider, "stop"):
                try:
                    await provider.stop()
                except Exception as exc:
                    errors.append((name, exc))

        self._initialized = False

        if errors:
            for name, exc in errors:
                logger.error("Error shutting down %s: %s", name, exc)
        else:
            logger.info("All hardware providers shut down successfully")

    # -- unified reading -----------------------------------------------------

    async def get_all_readings(self, splice_id: str) -> Dict[str, Any]:
        """Read from all sensors concurrently and return a unified dict.

        Args:
            splice_id: Identifier of the splice being inspected.

        Returns:
            Dict with keys ``splice_id``, ``timestamp``, ``vision``,
            ``thermal``, ``conductive``, ``mechanical``, ``belt_position``.
        """
        tasks = {}

        # Camera
        if self.camera is not None and self.camera.is_connected():
            tasks["vision"] = self._read_camera()
        # Thermal
        if self.thermal is not None:
            tasks["thermal"] = self.thermal.read()
        # Conductive
        if self.conductive is not None:
            tasks["conductive"] = self.conductive.read()
        # Mechanical
        if self.mechanical is not None:
            tasks["mechanical"] = self.mechanical.read()
        # Belt position
        if self.belt_position is not None and self.belt_position.is_connected():
            tasks["belt_position"] = self.belt_position.get_position()

        # Run all reads concurrently
        keys = list(tasks.keys())
        coros = list(tasks.values())
        results_list = await asyncio.gather(*coros, return_exceptions=True)

        results: Dict[str, Any] = {
            "splice_id": splice_id,
            "timestamp": time.time(),
        }

        for key, result in zip(keys, results_list):
            if isinstance(result, Exception):
                logger.error("Error reading %s: %s", key, result)
                results[key] = {"error": str(result)}
            else:
                results[key] = result

        # Fill in any missing sensor keys with None
        for key in ("vision", "thermal", "conductive", "mechanical", "belt_position"):
            if key not in results:
                results[key] = None

        return results

    async def _read_camera(self) -> Dict[str, Any]:
        """Read a frame from the camera, add it to the buffer, and return metadata."""
        frame, timestamp = await self.camera.get_frame()

        # Add to frame buffer
        if self.frame_buffer is not None:
            self.frame_buffer.add_frame(frame, timestamp)

        return {
            "frame_shape": list(frame.shape),
            "frame_dtype": str(frame.dtype),
            "mean_intensity": round(float(np.mean(frame)), 2),
            "timestamp": timestamp,
        }

    # -- status --------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return connection and readiness status for every component."""
        return {
            "initialized": self._initialized,
            "simulation_mode": self._config.SIMULATION_MODE,
            "camera": {
                "connected": self.camera.is_connected() if self.camera else False,
                "type": type(self.camera).__name__ if self.camera else None,
            },
            "thermal": {
                "enabled": self._config.THERMAL_ENABLED,
                "connected": self.thermal.is_connected() if self.thermal else False,
                "type": type(self.thermal).__name__ if self.thermal else None,
            },
            "conductive": {
                "enabled": self._config.CONDUCTIVE_ENABLED,
                "connected": self.conductive.is_connected() if self.conductive else False,
                "type": type(self.conductive).__name__ if self.conductive else None,
            },
            "mechanical": {
                "enabled": self._config.MECHANICAL_ENABLED,
                "connected": self.mechanical.is_connected() if self.mechanical else False,
                "type": type(self.mechanical).__name__ if self.mechanical else None,
            },
            "belt_position": {
                "connected": self.belt_position.is_connected() if self.belt_position else False,
                "type": type(self.belt_position).__name__ if self.belt_position else None,
            },
            "frame_buffer": {
                "active": self.frame_buffer is not None,
                "size": len(self.frame_buffer._buffer) if self.frame_buffer else 0,
                "capacity": self.frame_buffer._buffer.maxlen if self.frame_buffer else 0,
            },
        }

    # -- anomaly injection (simulation mode) ---------------------------------

    def set_anomaly(
        self,
        sensor_type: str,
        active: bool,
        intensity: float = 0.5,
    ) -> None:
        """Route an anomaly setting to the appropriate simulation provider.

        Args:
            sensor_type: One of ``"vision"``, ``"thermal"``, ``"conductive"``,
                         ``"mechanical"``.
            active: Whether the anomaly should be active.
            intensity: Anomaly strength in ``[0, 1]``.

        Raises:
            ValueError: If the sensor type is unknown.
            RuntimeError: If the provider is not a simulation provider.
        """
        sensor_type = sensor_type.lower()

        if sensor_type == "vision":
            if not isinstance(self.camera, SimulationCameraProvider):
                raise RuntimeError("Anomaly injection requires a simulation camera provider")
            if active:
                # Default to 'crack' if no mode specified; caller can also use
                # the provider directly for full control.
                self.camera.set_anomaly("crack", intensity)
            else:
                self.camera.set_anomaly(None)

        elif sensor_type == "thermal":
            if not isinstance(self.thermal, SimulationThermalProvider):
                raise RuntimeError("Anomaly injection requires a simulation thermal provider")
            self.thermal.set_anomaly(active, intensity)

        elif sensor_type == "conductive":
            if not isinstance(self.conductive, SimulationConductiveProvider):
                raise RuntimeError("Anomaly injection requires a simulation conductive provider")
            if active:
                self.conductive.trigger_break()
            else:
                self.conductive.restore_continuity()

        elif sensor_type == "mechanical":
            if not isinstance(self.mechanical, SimulationMechanicalProvider):
                raise RuntimeError("Anomaly injection requires a simulation mechanical provider")
            self.mechanical.set_anomaly(active, intensity)

        else:
            raise ValueError(
                f"Unknown sensor type '{sensor_type}'. "
                "Choose from: vision, thermal, conductive, mechanical"
            )

        logger.info(
            "Anomaly %s for %s (intensity=%.2f)",
            "activated" if active else "deactivated",
            sensor_type,
            intensity,
        )
