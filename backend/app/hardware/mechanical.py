"""Mechanical vibration sensor providers for splice monitoring.

The simulation provider generates realistic vibration waveforms with
proper RMS, peak, variance, and FFT-based frequency analysis.  When an
anomaly is active, sinusoidal components at characteristic fault
frequencies are injected into the signal.
"""

from abc import ABC, abstractmethod
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class MechanicalProvider(ABC):
    """Abstract vibration / mechanical sensor interface."""

    @abstractmethod
    async def read(self) -> Dict[str, Any]:
        """Take a single vibration reading.

        Returns:
            Dict with ``rms``, ``peak``, ``variance``,
            ``frequency_features``, ``anomaly_score``,
            ``raw_signal``, ``timestamp``.
        """

    @abstractmethod
    def is_connected(self) -> bool:
        """Return ``True`` when the sensor is ready."""


# ---------------------------------------------------------------------------
# Simulation provider
# ---------------------------------------------------------------------------


class SimulationMechanicalProvider(MechanicalProvider):
    """Generates synthetic accelerometer / vibration signals.

    Normal operation produces low-amplitude Gaussian noise.  When an
    anomaly is active, sinusoidal fault-frequency components at 50 Hz
    and 120 Hz are added and noise amplitude increases.
    """

    def __init__(self, sample_rate: int = 1000) -> None:
        self.sample_rate = sample_rate
        self._rng = np.random.default_rng()
        self._anomaly_active = False
        self._anomaly_intensity: float = 0.0
        self._connected = True
        # Number of samples per reading window (100 ms window by default)
        self._window_samples = max(sample_rate // 10, 64)

    # -- lifecycle -----------------------------------------------------------

    def is_connected(self) -> bool:
        return self._connected

    # -- anomaly control -----------------------------------------------------

    def set_anomaly(self, active: bool, intensity: float = 0.5) -> None:
        """Enable or disable a mechanical anomaly.

        Args:
            active: Whether the anomaly is present.
            intensity: Strength in ``[0, 1]``.
        """
        self._anomaly_active = active
        self._anomaly_intensity = float(np.clip(intensity, 0.0, 1.0))

    # -- reading -------------------------------------------------------------

    async def read(self) -> Dict[str, Any]:
        # Small delay to simulate ADC sampling
        await asyncio.sleep(0.01)

        now = time.time()
        signal = self._generate_signal()

        # Time-domain statistics
        rms = float(np.sqrt(np.mean(signal ** 2)))
        peak = float(np.max(np.abs(signal)))
        variance = float(np.var(signal))

        # Frequency-domain analysis via FFT
        freq_features = self._compute_frequency_features(signal)

        # Anomaly score: combine RMS deviation and spectral energy
        # Normal RMS is ~0.05; anomalous can go up to ~0.5+
        rms_score = min(rms / 0.5, 1.0)
        spectral_score = min(freq_features["spectral_energy"] / 0.1, 1.0)
        anomaly_score = round(float(0.6 * rms_score + 0.4 * spectral_score), 4)

        return {
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "variance": round(variance, 6),
            "frequency_features": freq_features,
            "anomaly_score": anomaly_score,
            "raw_signal": signal[:100].tolist(),
            "timestamp": now,
        }

    def _generate_signal(self) -> np.ndarray:
        """Build a single vibration waveform."""
        n = self._window_samples
        t = np.arange(n, dtype=np.float64) / self.sample_rate

        # Baseline: low-amplitude Gaussian noise
        noise_std = 0.05
        signal = self._rng.normal(0.0, noise_std, size=n)

        if self._anomaly_active:
            intensity = self._anomaly_intensity
            # Inject sinusoidal fault frequencies
            # 50 Hz: primary fault frequency (e.g. belt flap)
            signal += intensity * 0.3 * np.sin(2 * np.pi * 50 * t)
            # 120 Hz: harmonic / bearing defect frequency
            signal += intensity * 0.15 * np.sin(2 * np.pi * 120 * t + self._rng.uniform(0, 2 * np.pi))
            # Increase broadband noise level
            signal += self._rng.normal(0.0, 0.08 * intensity, size=n)

        return signal

    def _compute_frequency_features(self, signal: np.ndarray) -> Dict[str, Any]:
        """Compute FFT-based features from the waveform."""
        n = len(signal)
        fft_vals = np.fft.rfft(signal)
        fft_magnitude = np.abs(fft_vals) / n
        freqs = np.fft.rfftfreq(n, d=1.0 / self.sample_rate)

        # Dominant frequency (excluding DC component at index 0)
        if len(fft_magnitude) > 1:
            mag_no_dc = fft_magnitude[1:]
            freqs_no_dc = freqs[1:]
            dominant_idx = int(np.argmax(mag_no_dc))
            dominant_frequency = round(float(freqs_no_dc[dominant_idx]), 2)
            dominant_magnitude = round(float(mag_no_dc[dominant_idx]), 6)
        else:
            dominant_frequency = 0.0
            dominant_magnitude = 0.0

        # Total spectral energy (sum of squared magnitudes, excluding DC)
        spectral_energy = round(float(np.sum(fft_magnitude[1:] ** 2)), 6)

        # Harmonic ratio: energy in narrow bands around 50 and 120 Hz
        # vs. total energy
        harmonic_energy = 0.0
        for target_hz in (50.0, 120.0):
            band_mask = (freqs >= target_hz - 5) & (freqs <= target_hz + 5)
            harmonic_energy += float(np.sum(fft_magnitude[band_mask] ** 2))

        if spectral_energy > 0:
            harmonic_ratio = round(harmonic_energy / spectral_energy, 4)
        else:
            harmonic_ratio = 0.0

        return {
            "dominant_frequency": dominant_frequency,
            "dominant_magnitude": dominant_magnitude,
            "spectral_energy": spectral_energy,
            "harmonic_ratio": harmonic_ratio,
        }


# ---------------------------------------------------------------------------
# Real hardware provider (stub)
# ---------------------------------------------------------------------------


class RealMechanicalProvider(MechanicalProvider):
    """Interface for a real accelerometer / vibration sensor.

    Returns safe default values when the sensor is not connected.
    """

    def __init__(self, bus: int = 1, address: int = 0x68) -> None:
        self._bus = bus
        self._address = address
        self._connected = False
        logger.info("RealMechanicalProvider configured for I2C bus %d, address 0x%02X", bus, address)

    async def start(self) -> None:
        """Attempt to open the I2C device."""
        try:
            import smbus2  # type: ignore[import-untyped]
            self._i2c = smbus2.SMBus(self._bus)
            # Verify the device responds (e.g. MPU-6050 WHO_AM_I register)
            who_am_i = self._i2c.read_byte_data(self._address, 0x75)
            logger.info("Accelerometer WHO_AM_I: 0x%02X", who_am_i)
            self._connected = True
        except Exception:
            self._connected = False
            logger.warning(
                "Could not connect to accelerometer on bus %d addr 0x%02X",
                self._bus,
                self._address,
            )

    async def stop(self) -> None:
        """Close the I2C bus."""
        if hasattr(self, "_i2c") and self._i2c is not None:
            try:
                self._i2c.close()
            except Exception:
                logger.exception("Error closing I2C bus")
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    async def read(self) -> Dict[str, Any]:
        now = time.time()
        if not self._connected:
            return {
                "rms": 0.0,
                "peak": 0.0,
                "variance": 0.0,
                "frequency_features": {
                    "dominant_frequency": 0.0,
                    "dominant_magnitude": 0.0,
                    "spectral_energy": 0.0,
                    "harmonic_ratio": 0.0,
                },
                "anomaly_score": 0.0,
                "raw_signal": [],
                "timestamp": now,
                "error": "sensor_not_connected",
            }

        try:
            loop = asyncio.get_running_loop()
            raw_bytes = await loop.run_in_executor(
                None,
                self._i2c.read_i2c_block_data,
                self._address,
                0x3B,
                6,
            )
            # Convert raw bytes to acceleration (simplified for MPU-6050)
            ax = (raw_bytes[0] << 8 | raw_bytes[1]) / 16384.0
            ay = (raw_bytes[2] << 8 | raw_bytes[3]) / 16384.0
            az = (raw_bytes[4] << 8 | raw_bytes[5]) / 16384.0
            magnitude = float(np.sqrt(ax ** 2 + ay ** 2 + az ** 2))
            return {
                "rms": round(magnitude, 6),
                "peak": round(magnitude, 6),
                "variance": 0.0,
                "frequency_features": {
                    "dominant_frequency": 0.0,
                    "dominant_magnitude": 0.0,
                    "spectral_energy": 0.0,
                    "harmonic_ratio": 0.0,
                },
                "anomaly_score": 0.0,
                "raw_signal": [ax, ay, az],
                "timestamp": now,
            }
        except Exception as exc:
            logger.error("Mechanical read error: %s", exc)
            return {
                "rms": 0.0,
                "peak": 0.0,
                "variance": 0.0,
                "frequency_features": {
                    "dominant_frequency": 0.0,
                    "dominant_magnitude": 0.0,
                    "spectral_energy": 0.0,
                    "harmonic_ratio": 0.0,
                },
                "anomaly_score": 0.0,
                "raw_signal": [],
                "timestamp": now,
                "error": str(exc),
            }
