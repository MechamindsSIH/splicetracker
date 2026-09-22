"""Tests for processing logic.

The project does not have separate processing modules (thermal_processor.py,
mechanical_processor.py, signal_sync.py). Processing is done inline via the
hardware providers and the sensor fusion engine. These tests exercise the
data transformation and feature computation logic embedded in the hardware
providers, which serve as the processing layer.
"""

import pytest
import numpy as np

from backend.app.hardware.thermal import SimulationThermalProvider
from backend.app.hardware.mechanical import SimulationMechanicalProvider


class TestThermalProcessing:
    """Tests for thermal data processing: baseline tracking, delta calculation."""

    @pytest.fixture
    def provider(self):
        return SimulationThermalProvider(baseline=36.0)

    async def test_baseline_tracking(self, provider):
        """Baseline temperature is consistently reported."""
        for _ in range(5):
            reading = await provider.read()
            assert reading["baseline"] == 36.0

    async def test_delta_calculation(self, provider):
        """Delta temperature is the difference from baseline."""
        reading = await provider.read()
        expected_delta = reading["temperature"] - 36.0
        assert abs(reading["delta_temperature"] - expected_delta) < 0.1

    async def test_anomaly_score_mapping(self, provider):
        """Anomaly score maps deviation via an exponential function."""
        # Normal reading: small delta -> low score
        provider.set_anomaly(False)
        normal = await provider.read()
        assert normal["thermal_anomaly_score"] < 0.3

        # Anomalous reading: large delta -> high score
        provider.set_anomaly(True, intensity=1.0)
        hot = await provider.read()
        assert hot["thermal_anomaly_score"] > 0.7

    async def test_rate_of_change_computed(self, provider):
        """Rate of change is computed after at least two readings."""
        r1 = await provider.read()
        r2 = await provider.read()
        # The rate_of_change field should be present (may be 0 on first read)
        assert "rate_of_change" in r2
        # After 2 readings, it should be a numeric value
        assert isinstance(r2["rate_of_change"], float)

    async def test_history_accumulates(self, provider):
        """Provider accumulates reading history."""
        for _ in range(5):
            await provider.read()
        trend = provider.get_trend()
        assert len(trend) == 5
        for ts, temp in trend:
            assert ts > 0
            assert isinstance(temp, float)


class TestMechanicalProcessing:
    """Tests for mechanical signal feature computation."""

    @pytest.fixture
    def provider(self):
        return SimulationMechanicalProvider(sample_rate=1000)

    async def test_rms_computation(self, provider):
        """RMS is computed from the signal window."""
        reading = await provider.read()
        assert reading["rms"] > 0
        assert isinstance(reading["rms"], float)

    async def test_peak_exceeds_rms(self, provider):
        """Peak value is at least as large as RMS."""
        reading = await provider.read()
        assert reading["peak"] >= reading["rms"]

    async def test_variance_non_negative(self, provider):
        """Variance is non-negative."""
        reading = await provider.read()
        assert reading["variance"] >= 0

    async def test_fft_feature_computation(self, provider):
        """FFT features are computed correctly."""
        reading = await provider.read()
        ff = reading["frequency_features"]
        assert ff["dominant_frequency"] >= 0
        assert ff["spectral_energy"] >= 0
        assert 0 <= ff["harmonic_ratio"] <= 1.0

    async def test_anomaly_amplifies_features(self, provider):
        """Anomaly injection amplifies signal features."""
        provider.set_anomaly(False)
        normal = await provider.read()

        provider.set_anomaly(True, intensity=1.0)
        anomalous = await provider.read()

        # RMS should be higher with anomaly
        assert anomalous["rms"] > normal["rms"]

    async def test_raw_signal_provided(self, provider):
        """Raw signal snippet is included in reading."""
        reading = await provider.read()
        assert isinstance(reading["raw_signal"], list)
        assert len(reading["raw_signal"]) == 100  # first 100 samples


class TestSignalSynchronization:
    """Tests for time-window synchronization across sensors.

    The project synchronizes sensor readings by reading all sensors
    concurrently (asyncio.gather in HardwareManager.get_all_readings).
    We verify that readings from different providers have close timestamps.
    """

    async def test_concurrent_timestamps_close(self):
        """Readings taken concurrently have timestamps within a reasonable window."""
        import asyncio

        thermal = SimulationThermalProvider(baseline=36.0)
        mechanical = SimulationMechanicalProvider()

        # Read both concurrently
        t_reading, m_reading = await asyncio.gather(
            thermal.read(),
            mechanical.read(),
        )

        # Timestamps should be within 1 second of each other
        dt = abs(t_reading["timestamp"] - m_reading["timestamp"])
        assert dt < 1.0

    async def test_sequential_timestamp_ordering(self):
        """Sequential readings have monotonically increasing timestamps."""
        thermal = SimulationThermalProvider(baseline=36.0)

        r1 = await thermal.read()
        r2 = await thermal.read()
        r3 = await thermal.read()

        assert r1["timestamp"] <= r2["timestamp"] <= r3["timestamp"]
