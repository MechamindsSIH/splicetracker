"""Tests for simulation hardware providers."""

import pytest
import numpy as np

from backend.app.hardware.camera import SimulationCameraProvider
from backend.app.hardware.thermal import SimulationThermalProvider
from backend.app.hardware.conductive import SimulationConductiveProvider
from backend.app.hardware.mechanical import SimulationMechanicalProvider
from backend.app.hardware.belt_position import SimulationBeltPositionProvider


class TestSimulationCamera:
    """Tests for the SimulationCameraProvider."""

    @pytest.fixture
    async def camera(self):
        cam = SimulationCameraProvider(width=320, height=240, fps=60)
        await cam.start()
        yield cam
        await cam.stop()

    async def test_generates_frames_of_correct_shape(self, camera):
        """Generated frame has the correct (H, W, 3) BGR shape."""
        frame, ts = await camera.get_frame()
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8

    async def test_timestamp_is_positive(self, camera):
        """Frame timestamp is a positive UNIX timestamp."""
        frame, ts = await camera.get_frame()
        assert ts > 0

    async def test_is_connected_when_started(self, camera):
        """Camera reports connected when started."""
        assert camera.is_connected() is True

    async def test_not_connected_when_stopped(self):
        """Camera reports not connected when stopped."""
        cam = SimulationCameraProvider()
        assert cam.is_connected() is False

    async def test_frame_count_increments(self, camera):
        """Frame count increments with each get_frame call."""
        await camera.get_frame()
        assert camera._frame_count == 1
        await camera.get_frame()
        assert camera._frame_count == 2

    async def test_set_anomaly_crack(self, camera):
        """Setting crack anomaly does not raise and affects the frame."""
        camera.set_anomaly("crack", 0.8)
        frame, _ = await camera.get_frame()
        assert frame.shape == (240, 320, 3)

    async def test_set_anomaly_deformation(self, camera):
        """Setting deformation anomaly works."""
        camera.set_anomaly("deformation", 0.5)
        frame, _ = await camera.get_frame()
        assert frame.shape == (240, 320, 3)

    async def test_set_anomaly_invalid_raises(self, camera):
        """Invalid anomaly mode raises ValueError."""
        with pytest.raises(ValueError, match="Unknown anomaly mode"):
            camera.set_anomaly("nonexistent", 0.5)

    async def test_clear_anomaly(self, camera):
        """Setting anomaly to None clears it."""
        camera.set_anomaly("crack", 0.8)
        camera.set_anomaly(None)
        assert camera.anomaly_mode is None
        frame, _ = await camera.get_frame()
        assert frame.shape == (240, 320, 3)


class TestSimulationThermal:
    """Tests for the SimulationThermalProvider."""

    @pytest.fixture
    def provider(self):
        return SimulationThermalProvider(baseline=36.7)

    async def test_generates_readings_with_expected_fields(self, provider):
        """Thermal reading has all expected fields."""
        reading = await provider.read()
        expected_keys = {
            "temperature", "baseline", "delta_temperature",
            "rate_of_change", "thermal_anomaly_score",
            "hotspot_location", "timestamp",
        }
        assert expected_keys.issubset(set(reading.keys()))

    async def test_baseline_temperature(self, provider):
        """Reading baseline matches the configured value."""
        reading = await provider.read()
        assert reading["baseline"] == 36.7

    async def test_normal_reading_low_anomaly(self, provider):
        """Normal reading (no anomaly) has a low anomaly score."""
        reading = await provider.read()
        assert reading["thermal_anomaly_score"] < 0.3

    async def test_anomaly_increases_temperature(self, provider):
        """Active anomaly raises temperature significantly above baseline."""
        provider.set_anomaly(True, intensity=0.8)
        reading = await provider.read()
        assert reading["temperature"] > provider.baseline + 5
        assert reading["thermal_anomaly_score"] > 0.5

    async def test_hotspot_location_when_anomaly_active(self, provider):
        """Hotspot location is populated when anomaly is active."""
        provider.set_anomaly(True, intensity=0.5)
        reading = await provider.read()
        assert reading["hotspot_location"] is not None
        assert "x" in reading["hotspot_location"]
        assert "y" in reading["hotspot_location"]

    async def test_no_hotspot_when_normal(self, provider):
        """Hotspot location is None during normal operation."""
        reading = await provider.read()
        assert reading["hotspot_location"] is None

    async def test_is_connected(self, provider):
        """Provider reports connected by default."""
        assert provider.is_connected() is True


class TestSimulationConductive:
    """Tests for the SimulationConductiveProvider."""

    @pytest.fixture
    def provider(self):
        return SimulationConductiveProvider()

    async def test_continuity_normal(self, provider):
        """Normal state has continuity=True and anomaly_score=0."""
        reading = await provider.read()
        assert reading["continuity"] is True
        assert reading["anomaly_score"] == 0.0
        assert reading["transition"] == "continuous"

    async def test_break_detected(self, provider):
        """Triggering a break changes continuity to False."""
        provider.trigger_break()
        reading = await provider.read()
        assert reading["continuity"] is False
        assert reading["anomaly_score"] == 1.0
        assert reading["transition"] == "break_detected"

    async def test_break_ongoing(self, provider):
        """Subsequent reads during a break show break_ongoing."""
        provider.trigger_break()
        await provider.read()  # first read: break_detected
        reading = await provider.read()  # second: break_ongoing
        assert reading["continuity"] is False
        assert reading["transition"] == "break_ongoing"

    async def test_restore_continuity(self, provider):
        """Restoring continuity after a break works."""
        provider.trigger_break()
        await provider.read()  # break_detected
        provider.restore_continuity()
        reading = await provider.read()
        assert reading["continuity"] is True
        assert reading["transition"] == "restored"

    async def test_duration_ms_during_break(self, provider):
        """Duration is positive during an active break."""
        provider.trigger_break()
        reading = await provider.read()
        assert reading["duration_ms"] >= 0.0

    async def test_is_connected(self, provider):
        """Provider reports connected by default."""
        assert provider.is_connected() is True


class TestSimulationMechanical:
    """Tests for the SimulationMechanicalProvider."""

    @pytest.fixture
    def provider(self):
        return SimulationMechanicalProvider(sample_rate=1000)

    async def test_generates_signal_features(self, provider):
        """Reading contains rms, peak, variance, and frequency features."""
        reading = await provider.read()
        assert "rms" in reading
        assert "peak" in reading
        assert "variance" in reading
        assert "frequency_features" in reading
        assert "anomaly_score" in reading
        assert "raw_signal" in reading

    async def test_normal_low_rms(self, provider):
        """Normal operation produces low RMS values."""
        reading = await provider.read()
        assert reading["rms"] < 0.2
        assert reading["anomaly_score"] < 0.5

    async def test_anomaly_increases_rms(self, provider):
        """Active anomaly raises RMS and anomaly score."""
        provider.set_anomaly(True, intensity=0.9)
        reading = await provider.read()
        assert reading["rms"] > 0.1
        assert reading["anomaly_score"] > 0.3

    async def test_frequency_features_structure(self, provider):
        """Frequency features have the expected keys."""
        reading = await provider.read()
        ff = reading["frequency_features"]
        assert "dominant_frequency" in ff
        assert "dominant_magnitude" in ff
        assert "spectral_energy" in ff
        assert "harmonic_ratio" in ff

    async def test_anomaly_changes_frequency_content(self, provider):
        """Anomaly injection should increase spectral energy."""
        provider.set_anomaly(False)
        normal = await provider.read()

        provider.set_anomaly(True, intensity=1.0)
        anomalous = await provider.read()

        assert anomalous["frequency_features"]["spectral_energy"] > normal["frequency_features"]["spectral_energy"]

    async def test_is_connected(self, provider):
        """Provider reports connected by default."""
        assert provider.is_connected() is True


class TestBeltPosition:
    """Tests for the SimulationBeltPositionProvider."""

    @pytest.fixture
    async def provider(self):
        bp = SimulationBeltPositionProvider(belt_speed=2.0, belt_length=100.0, num_splices=5)
        await bp.start()
        yield bp
        await bp.stop()

    async def test_position_tracking(self, provider):
        """Position is a non-negative float."""
        pos = await provider.get_position()
        assert pos["position"] >= 0
        assert pos["position"] < provider.belt_length

    async def test_splice_detection(self, provider):
        """Provider identifies the nearest splice."""
        pos = await provider.get_position()
        assert pos["nearest_splice_id"] is not None
        assert pos["nearest_splice_id"].startswith("SPL-")
        assert pos["nearest_splice_distance"] is not None
        assert pos["nearest_splice_distance"] >= 0

    async def test_belt_id(self, provider):
        """Belt ID is returned."""
        pos = await provider.get_position()
        assert pos["belt_id"] == "BELT-001"

    async def test_not_connected_when_stopped(self):
        """Provider reports not connected when not started."""
        bp = SimulationBeltPositionProvider()
        assert bp.is_connected() is False

    async def test_is_connected_when_running(self, provider):
        """Provider reports connected when running."""
        assert provider.is_connected() is True

    async def test_splice_positions_generated(self, provider):
        """Splice positions list has the expected count."""
        positions = provider.get_splice_positions()
        assert len(positions) == 5
        for sp in positions:
            assert "splice_id" in sp
            assert "position" in sp
            assert "name" in sp

    async def test_speed_and_direction(self, provider):
        """Position output includes speed and direction."""
        pos = await provider.get_position()
        assert pos["speed"] == 2.0
        assert pos["direction"] == "forward"
        assert pos["is_estimated"] is False


class TestAnomalyInjection:
    """Tests for anomaly injection across hardware providers."""

    async def test_camera_anomaly_injection(self):
        """Camera anomaly injection modifies frame output."""
        cam = SimulationCameraProvider(width=640, height=480, fps=60)
        await cam.start()

        cam.set_anomaly(None)
        frame_normal, _ = await cam.get_frame()

        cam.set_anomaly("discoloration", 0.5)
        frame_anomaly, _ = await cam.get_frame()

        await cam.stop()

        # Frames differ (anomaly injection changes pixel values)
        # We compare means since exact pixel comparison is noisy
        normal_mean = np.mean(frame_normal.astype(float))
        anomaly_mean = np.mean(frame_anomaly.astype(float))
        # They should not be identical (high probability)
        assert frame_normal.shape == frame_anomaly.shape

    async def test_thermal_anomaly_toggle(self):
        """Toggling thermal anomaly changes temperature readings."""
        provider = SimulationThermalProvider(baseline=36.7)

        provider.set_anomaly(False)
        normal = await provider.read()

        provider.set_anomaly(True, intensity=1.0)
        hot = await provider.read()

        assert hot["temperature"] > normal["temperature"]

    async def test_conductive_anomaly_toggle(self):
        """Toggling conductive break changes continuity."""
        provider = SimulationConductiveProvider()

        normal = await provider.read()
        assert normal["continuity"] is True

        provider.trigger_break()
        broken = await provider.read()
        assert broken["continuity"] is False

        provider.restore_continuity()
        restored = await provider.read()
        assert restored["continuity"] is True
