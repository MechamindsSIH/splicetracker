"""Mechanical / vibration signal processing for splice monitoring.

Analyses vibration readings in both time and frequency domains to detect
mechanical faults (bearing wear, belt misalignment, splice separation).
"""

from collections import deque
from typing import Optional

import numpy as np


class MechanicalProcessor:
    """Processes mechanical vibration sensor data and performs spectral
    analysis, baseline tracking, and anomaly scoring.
    """

    def __init__(self, sample_rate: int = 1000):
        self.sample_rate: int = sample_rate
        self.baseline_rms: Optional[float] = None
        self.baseline_peak: Optional[float] = None
        self.history: deque[dict] = deque(maxlen=50)

        # Frequency band edges (Hz)
        self._low_band = (0.0, 50.0)
        self._mid_band = (50.0, 200.0)
        self._high_band = (200.0, float(sample_rate / 2))

        # Baseline EMA smoothing factor
        self._ema_alpha: float = 0.15

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process(self, reading: dict) -> dict:
        """Process a mechanical vibration reading.

        Parameters
        ----------
        reading : dict
            Expected keys:
            - ``rms`` (float): root-mean-square of the signal window.
            - ``peak`` (float): peak absolute value.
            - ``variance`` (float): signal variance.
            - ``raw_signal`` (list[float], optional): time-domain samples
              for spectral analysis.
            - ``timestamp`` (float): POSIX timestamp.
            Additional keys are passed through.

        Returns
        -------
        dict
            Original fields plus:
            ``processed_rms_deviation``, ``processed_peak_deviation``,
            ``frequency_analysis``, ``processed_anomaly_score``,
            ``baseline_rms``, ``baseline_peak``, ``readings_count``.
        """
        rms = float(reading.get("rms", 0.0))
        peak = float(reading.get("peak", 0.0))
        variance = float(reading.get("variance", 0.0))
        raw_signal = reading.get("raw_signal")

        # Validate
        if np.isnan(rms) or np.isnan(peak):
            rms = 0.0 if np.isnan(rms) else rms
            peak = 0.0 if np.isnan(peak) else peak

        # Clamp to physically reasonable range (g's for vibration)
        rms = float(np.clip(rms, 0.0, 100.0))
        peak = float(np.clip(peak, 0.0, 200.0))

        # Update baselines (exponential moving average)
        if self.baseline_rms is None:
            self.baseline_rms = rms
            self.baseline_peak = peak
        else:
            self.baseline_rms = (1.0 - self._ema_alpha) * self.baseline_rms + self._ema_alpha * rms
            self.baseline_peak = (1.0 - self._ema_alpha) * self.baseline_peak + self._ema_alpha * peak

        # Deviations from baseline
        rms_deviation = self._safe_deviation(rms, self.baseline_rms)
        peak_deviation = self._safe_deviation(peak, self.baseline_peak)

        # Frequency-domain analysis
        freq_analysis = self._analyze_spectrum(raw_signal)

        # Variance tracking
        variance_deviation = 0.0
        if len(self.history) >= 3:
            hist_variances = [h.get("variance", 0.0) for h in self.history]
            baseline_var = float(np.mean(hist_variances))
            variance_deviation = self._safe_deviation(variance, baseline_var)

        # Anomaly score
        high_freq_ratio = freq_analysis.get("high_band_ratio", 0.0) if freq_analysis else 0.0
        anomaly_score = self._compute_anomaly_score(
            rms_deviation, peak_deviation, high_freq_ratio, variance_deviation
        )

        # Store in history
        entry = {
            "rms": rms,
            "peak": peak,
            "variance": variance,
            "anomaly_score": anomaly_score,
            "timestamp": reading.get("timestamp", 0.0),
        }
        self.history.append(entry)

        result = dict(reading)
        # Remove raw signal from output to avoid bloating
        result.pop("raw_signal", None)
        result.update({
            "processed_rms_deviation": round(rms_deviation, 4),
            "processed_peak_deviation": round(peak_deviation, 4),
            "frequency_analysis": freq_analysis,
            "processed_anomaly_score": round(anomaly_score, 4),
            "baseline_rms": round(self.baseline_rms, 4),
            "baseline_peak": round(self.baseline_peak, 4) if self.baseline_peak is not None else 0.0,
            "readings_count": len(self.history),
        })
        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_deviation(current: float, baseline: float) -> float:
        """Normalised deviation clamped to [0, 1]."""
        if baseline < 1e-9:
            return min(abs(current), 1.0)
        return min(abs(current - baseline) / baseline, 1.0)

    def _analyze_spectrum(self, raw_signal) -> dict:
        """Perform FFT-based spectral analysis on the raw vibration signal.

        Returns an empty dict when no raw signal is available.
        """
        if raw_signal is None or len(raw_signal) < 4:
            return {}

        signal = np.asarray(raw_signal, dtype=np.float64)

        # Remove NaN / Inf
        if np.any(~np.isfinite(signal)):
            signal = np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0)

        n = len(signal)
        # Apply Hann window to reduce spectral leakage
        window = np.hanning(n)
        windowed = signal * window

        # Real FFT
        fft_vals = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(n, d=1.0 / self.sample_rate)

        # Power spectrum (magnitude squared, normalised)
        power = np.abs(fft_vals) ** 2
        total_power = float(np.sum(power))
        if total_power < 1e-12:
            return {
                "dominant_frequency": 0.0,
                "spectral_centroid": 0.0,
                "low_band_ratio": 0.0,
                "mid_band_ratio": 0.0,
                "high_band_ratio": 0.0,
                "total_power": 0.0,
            }

        # Dominant frequency (frequency of max power, skip DC at index 0)
        if len(power) > 1:
            dominant_idx = int(np.argmax(power[1:])) + 1
            dominant_frequency = float(freqs[dominant_idx])
        else:
            dominant_frequency = 0.0

        # Spectral centroid
        spectral_centroid = float(np.sum(freqs * power) / total_power)

        # Band energy ratios
        low_mask = (freqs >= self._low_band[0]) & (freqs < self._low_band[1])
        mid_mask = (freqs >= self._mid_band[0]) & (freqs < self._mid_band[1])
        high_mask = (freqs >= self._high_band[0]) & (freqs <= self._high_band[1])

        low_energy = float(np.sum(power[low_mask]))
        mid_energy = float(np.sum(power[mid_mask]))
        high_energy = float(np.sum(power[high_mask]))

        low_ratio = low_energy / total_power
        mid_ratio = mid_energy / total_power
        high_ratio = high_energy / total_power

        return {
            "dominant_frequency": round(dominant_frequency, 2),
            "spectral_centroid": round(spectral_centroid, 2),
            "low_band_ratio": round(low_ratio, 4),
            "mid_band_ratio": round(mid_ratio, 4),
            "high_band_ratio": round(high_ratio, 4),
            "total_power": round(total_power, 4),
        }

    @staticmethod
    def _compute_anomaly_score(
        rms_dev: float, peak_dev: float, high_freq_ratio: float, var_dev: float
    ) -> float:
        """Weighted anomaly score in [0, 1].

        Weights:
        - RMS deviation from baseline: 0.3
        - Peak deviation: 0.2
        - High-frequency energy ratio: 0.3 (mechanical faults manifest
          as elevated high-frequency content)
        - Variance change: 0.2
        """
        score = (
            0.3 * min(rms_dev, 1.0)
            + 0.2 * min(peak_dev, 1.0)
            + 0.3 * min(high_freq_ratio, 1.0)
            + 0.2 * min(var_dev, 1.0)
        )
        return float(np.clip(score, 0.0, 1.0))
