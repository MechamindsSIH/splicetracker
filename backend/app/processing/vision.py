"""Vision processing pipeline for conveyor-belt splice monitoring.

Processes camera frames through a multi-stage pipeline: preprocessing,
ROI detection, feature extraction, anomaly scoring, defect classification,
optical flow, and deformation analysis.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple

import cv2
import numpy as np


class VisionProcessor:
    """Processes camera frames to detect and classify splice defects."""

    def __init__(self, config: Optional[dict] = None):
        config = config or {}
        self.roi_margin: int = config.get("roi_margin", 50)
        self.anomaly_threshold: float = config.get("anomaly_threshold", 0.5)
        self.prev_frame: Optional[np.ndarray] = None
        self.prev_features: Optional[dict] = None
        self.frame_count: int = 0

        # Baseline feature statistics for anomaly detection.
        # These represent a healthy splice under normal operating conditions.
        self.baseline_edge_density: float = config.get("baseline_edge_density", 0.05)
        self.baseline_texture_variance: float = config.get("baseline_texture_variance", 400.0)
        self.baseline_mean_intensity: float = config.get("baseline_mean_intensity", 128.0)
        self.baseline_contour_area_ratio: float = config.get("baseline_contour_area_ratio", 0.02)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_frame(self, frame: np.ndarray, timestamp: float) -> dict:
        """Run the full vision pipeline on a single camera frame.

        Parameters
        ----------
        frame : np.ndarray
            BGR image captured from the camera.
        timestamp : float
            POSIX timestamp of the capture moment.

        Returns
        -------
        dict
            Comprehensive analysis result containing detection flags,
            features, optical-flow data, and deformation metrics.
        """
        frame_id = str(uuid.uuid4())
        self.frame_count += 1

        # Stage 1 -- preprocessing
        grayscale, preprocessed = self._preprocess(frame)

        # Stage 2 -- ROI detection
        roi_info = self._detect_roi(preprocessed)

        # Extract the ROI sub-image for downstream analysis
        if roi_info["detected"]:
            x, y = roi_info["x"], roi_info["y"]
            w, h = roi_info["width"], roi_info["height"]
            roi_img = preprocessed[y : y + h, x : x + w]
        else:
            roi_img = preprocessed

        # Stage 3 -- feature extraction
        features = self._extract_features(roi_img)

        # Stage 4 -- anomaly scoring
        anomaly_score, deviations = self._detect_anomaly(features)

        # Stage 5 -- defect classification
        defect_type, defect_confidence = self._classify_defect(features, anomaly_score)

        # Stage 6 -- optical flow (requires a previous frame)
        optical_flow: dict = {}
        deformation: dict = {}
        if self.prev_frame is not None:
            prev_roi = self.prev_frame
            if roi_info["detected"]:
                x, y = roi_info["x"], roi_info["y"]
                w, h = roi_info["width"], roi_info["height"]
                ph, pw = self.prev_frame.shape[:2]
                # Clamp to previous frame dimensions
                px, py = min(x, pw - 1), min(y, ph - 1)
                pxw = min(x + w, pw)
                pyh = min(y + h, ph)
                if pxw > px and pyh > py:
                    prev_roi = self.prev_frame[py:pyh, px:pxw]

            # Resize if shapes differ so calcOpticalFlowFarneback succeeds
            if prev_roi.shape != roi_img.shape:
                prev_roi = cv2.resize(prev_roi, (roi_img.shape[1], roi_img.shape[0]))

            optical_flow = self._compute_optical_flow(roi_img, prev_roi)

            if optical_flow.get("has_motion", False):
                deformation = self._analyze_deformation(optical_flow["_flow_field"])

            # Strip the internal numpy field before returning
            optical_flow.pop("_flow_field", None)

        # Persist preprocessed grayscale for next-frame flow computation
        self.prev_frame = preprocessed.copy()
        self.prev_features = features

        splice_detected = roi_info["detected"]
        defect_detected = defect_type is not None

        bounding_region: Optional[dict] = None
        if defect_detected and roi_info["detected"]:
            bounding_region = {
                "x": roi_info["x"],
                "y": roi_info["y"],
                "width": roi_info["width"],
                "height": roi_info["height"],
            }

        return {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "roi": roi_info,
            "splice_detected": splice_detected,
            "defect_detected": defect_detected,
            "defect_type": defect_type,
            "defect_confidence": round(defect_confidence, 4) if defect_confidence else 0.0,
            "bounding_region": bounding_region,
            "features": features,
            "optical_flow": optical_flow,
            "deformation": deformation,
            "anomaly_score": round(anomaly_score, 4),
        }

    # ------------------------------------------------------------------
    # Internal pipeline stages
    # ------------------------------------------------------------------

    def _preprocess(self, frame: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Convert to grayscale, denoise, and normalize histogram.

        Returns (grayscale_original, preprocessed).
        """
        if len(frame.shape) == 3 and frame.shape[2] == 3:
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        elif len(frame.shape) == 3 and frame.shape[2] == 4:
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            grayscale = frame.copy()

        # Gaussian blur for noise reduction (kernel must be odd)
        blurred = cv2.GaussianBlur(grayscale, (5, 5), sigmaX=1.0)

        # Histogram equalization to normalize contrast
        preprocessed = cv2.equalizeHist(blurred)

        return grayscale, preprocessed

    def _detect_roi(self, frame: np.ndarray) -> dict:
        """Detect the splice region using horizontal projection profiling.

        Splices appear as a horizontal band whose mean row intensity
        deviates from the frame average.
        """
        h, w = frame.shape[:2]

        # Compute row-wise mean intensity
        row_means = np.mean(frame, axis=1).astype(np.float64)
        overall_mean = np.mean(row_means)
        overall_std = np.std(row_means)

        if overall_std < 1.0:
            # Very uniform image -- fall back to centre third
            third = h // 3
            return {
                "x": 0,
                "y": third,
                "width": w,
                "height": third,
                "detected": False,
            }

        # Rows whose intensity deviates by more than 1 std from the mean
        threshold = overall_mean + overall_std
        deviant_mask = np.abs(row_means - overall_mean) > (overall_std * 1.0)
        deviant_rows = np.where(deviant_mask)[0]

        if len(deviant_rows) < 3:
            # No clear band -- fall back to centre third
            third = h // 3
            return {
                "x": 0,
                "y": third,
                "width": w,
                "height": third,
                "detected": False,
            }

        # Group contiguous deviant rows into bands, pick the largest
        bands: list[Tuple[int, int]] = []
        start = deviant_rows[0]
        prev = deviant_rows[0]
        for r in deviant_rows[1:]:
            if r - prev > 3:  # allow small gaps of up to 3 rows
                bands.append((start, prev))
                start = r
            prev = r
        bands.append((start, prev))

        # Select the widest band
        best_band = max(bands, key=lambda b: b[1] - b[0])
        y_start = max(0, best_band[0] - self.roi_margin)
        y_end = min(h, best_band[1] + self.roi_margin)
        band_height = y_end - y_start

        if band_height < 5:
            third = h // 3
            return {
                "x": 0,
                "y": third,
                "width": w,
                "height": third,
                "detected": False,
            }

        return {
            "x": 0,
            "y": int(y_start),
            "width": int(w),
            "height": int(band_height),
            "detected": True,
        }

    def _extract_features(self, roi: np.ndarray) -> dict:
        """Extract a comprehensive set of visual features from the ROI."""
        if roi.size == 0:
            return {
                "edge_density": 0.0,
                "mean_intensity": 0.0,
                "std_intensity": 0.0,
                "texture_variance": 0.0,
                "gradient_magnitude": 0.0,
                "histogram": [0.0] * 16,
                "contour_count": 0,
                "contour_area_ratio": 0.0,
            }

        total_pixels = roi.shape[0] * roi.shape[1]

        # --- Edge density via Canny ---
        edges = cv2.Canny(roi, threshold1=50, threshold2=150)
        edge_pixels = np.count_nonzero(edges)
        edge_density = float(edge_pixels) / total_pixels

        # --- Intensity statistics ---
        mean_intensity = float(np.mean(roi))
        std_intensity = float(np.std(roi))

        # --- Texture: variance of the Laplacian ---
        laplacian = cv2.Laplacian(roi, cv2.CV_64F)
        texture_variance = float(np.var(laplacian))

        # --- Gradient magnitude via Sobel ---
        sobel_x = cv2.Sobel(roi, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(roi, cv2.CV_64F, 0, 1, ksize=3)
        gradient_mag = np.sqrt(sobel_x ** 2 + sobel_y ** 2)
        gradient_magnitude = float(np.mean(gradient_mag))

        # --- Normalized 16-bin histogram ---
        hist = cv2.calcHist([roi], [0], None, [16], [0, 256])
        hist = hist.flatten().astype(np.float64)
        hist_sum = hist.sum()
        if hist_sum > 0:
            hist = hist / hist_sum
        histogram = [round(float(v), 6) for v in hist]

        # --- Contour analysis ---
        _, binary = cv2.threshold(edges, 127, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contour_count = len(contours)
        total_contour_area = sum(cv2.contourArea(c) for c in contours)
        contour_area_ratio = float(total_contour_area) / total_pixels if total_pixels > 0 else 0.0

        return {
            "edge_density": round(edge_density, 6),
            "mean_intensity": round(mean_intensity, 4),
            "std_intensity": round(std_intensity, 4),
            "texture_variance": round(texture_variance, 4),
            "gradient_magnitude": round(gradient_magnitude, 4),
            "histogram": histogram,
            "contour_count": contour_count,
            "contour_area_ratio": round(contour_area_ratio, 6),
        }

    def _detect_anomaly(self, features: dict) -> Tuple[float, dict]:
        """Score how anomalous the current features are relative to baseline.

        Returns (anomaly_score in [0, 1], deviations_dict).
        """

        def _deviation(current: float, baseline: float) -> float:
            """Normalised absolute deviation, clamped to [0, 1]."""
            if baseline == 0:
                return min(abs(current), 1.0)
            return min(abs(current - baseline) / baseline, 1.0)

        edge_dev = _deviation(features["edge_density"], self.baseline_edge_density)
        texture_dev = _deviation(features["texture_variance"], self.baseline_texture_variance)
        intensity_dev = _deviation(features["mean_intensity"], self.baseline_mean_intensity)
        contour_dev = _deviation(features["contour_area_ratio"], self.baseline_contour_area_ratio)

        # Weighted combination
        anomaly_score = (
            0.30 * edge_dev
            + 0.25 * texture_dev
            + 0.15 * intensity_dev
            + 0.30 * contour_dev
        )
        anomaly_score = float(np.clip(anomaly_score, 0.0, 1.0))

        deviations = {
            "edge_density_deviation": round(edge_dev, 4),
            "texture_variance_deviation": round(texture_dev, 4),
            "intensity_deviation": round(intensity_dev, 4),
            "contour_area_deviation": round(contour_dev, 4),
        }

        return anomaly_score, deviations

    def _classify_defect(
        self, features: dict, anomaly_score: float
    ) -> Tuple[Optional[str], float]:
        """Classify the defect type from feature patterns.

        Returns (defect_type, confidence).  defect_type is ``None``
        when the anomaly score is below threshold.
        """
        if anomaly_score < self.anomaly_threshold:
            return None, 0.0

        edge = features["edge_density"]
        texture = features["texture_variance"]
        intensity = features["mean_intensity"]
        contour_count = features["contour_count"]
        contour_area = features["contour_area_ratio"]
        gradient = features["gradient_magnitude"]

        # Build a simple score for each defect class
        scores: dict[str, float] = {}

        # Crack: high edge density, high gradient, low local intensity
        crack_score = 0.0
        if edge > self.baseline_edge_density * 1.8:
            crack_score += 0.4
        if gradient > 30.0:
            crack_score += 0.3
        if intensity < self.baseline_mean_intensity * 0.75:
            crack_score += 0.3
        scores["crack"] = crack_score

        # Deformation: high texture variance + moderate edge density
        deformation_score = 0.0
        if texture > self.baseline_texture_variance * 1.5:
            deformation_score += 0.5
        if self.baseline_edge_density * 0.8 <= edge <= self.baseline_edge_density * 2.5:
            deformation_score += 0.3
        if contour_area > self.baseline_contour_area_ratio * 1.2:
            deformation_score += 0.2
        scores["deformation"] = deformation_score

        # Discoloration: significant intensity deviation, low edge density
        discoloration_score = 0.0
        intensity_ratio = abs(intensity - self.baseline_mean_intensity) / max(self.baseline_mean_intensity, 1.0)
        if intensity_ratio > 0.25:
            discoloration_score += 0.5
        if edge < self.baseline_edge_density * 1.3:
            discoloration_score += 0.3
        if texture < self.baseline_texture_variance * 1.2:
            discoloration_score += 0.2
        scores["discoloration"] = discoloration_score

        # Edge damage: high contour count
        edge_damage_score = 0.0
        if contour_count > 15:
            edge_damage_score += 0.5
        if edge > self.baseline_edge_density * 1.5:
            edge_damage_score += 0.3
        if contour_area > self.baseline_contour_area_ratio * 2.0:
            edge_damage_score += 0.2
        scores["edge_damage"] = edge_damage_score

        # Surface wear: moderate anomaly spread across multiple features
        wear_score = 0.0
        mild_deviations = 0
        if edge > self.baseline_edge_density * 1.2:
            mild_deviations += 1
        if texture > self.baseline_texture_variance * 1.2:
            mild_deviations += 1
        if intensity_ratio > 0.15:
            mild_deviations += 1
        if contour_count > 8:
            mild_deviations += 1
        if mild_deviations >= 3:
            wear_score = 0.3 + 0.15 * mild_deviations
        scores["surface_wear"] = min(wear_score, 1.0)

        # Pick the highest-scoring class
        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_type]

        if best_score < 0.2:
            return None, 0.0

        # Confidence blends the class score with the anomaly score
        confidence = float(np.clip(0.5 * best_score + 0.5 * anomaly_score, 0.0, 1.0))

        return best_type, round(confidence, 4)

    def _compute_optical_flow(
        self, current_gray: np.ndarray, previous_gray: np.ndarray
    ) -> dict:
        """Dense optical flow via Farneback.

        The returned dict includes a private ``_flow_field`` key
        carrying the raw flow array for downstream deformation analysis;
        callers should strip it before serialising.
        """
        flow = cv2.calcOpticalFlowFarneback(
            previous_gray,
            current_gray,
            None,  # type: ignore[arg-type]
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            poly_n=5,
            poly_sigma=1.2,
            flags=0,
        )

        flow_x = flow[..., 0]
        flow_y = flow[..., 1]
        magnitude = np.sqrt(flow_x ** 2 + flow_y ** 2)

        mean_mag = float(np.mean(magnitude))
        max_mag = float(np.max(magnitude))
        flow_var = float(np.var(magnitude))
        has_motion = max_mag > 0.5  # half-pixel threshold

        return {
            "mean_flow_x": round(float(np.mean(flow_x)), 4),
            "mean_flow_y": round(float(np.mean(flow_y)), 4),
            "max_magnitude": round(max_mag, 4),
            "mean_magnitude": round(mean_mag, 4),
            "flow_variance": round(flow_var, 4),
            "has_motion": bool(has_motion),
            "_flow_field": flow,
        }

    def _analyze_deformation(self, flow_field: np.ndarray) -> dict:
        """Derive strain-like deformation metrics from the optical flow field."""
        u = flow_field[..., 0]  # horizontal displacement
        v = flow_field[..., 1]  # vertical displacement

        # Spatial gradients of the displacement field (strain tensor components)
        du_dy, du_dx = np.gradient(u)
        dv_dy, dv_dx = np.gradient(v)

        strain_xx = du_dx  # normal strain in x
        strain_yy = dv_dy  # normal strain in y
        shear = 0.5 * (du_dy + dv_dx)  # engineering shear / 2

        mean_strain_xx = float(np.mean(np.abs(strain_xx)))
        mean_strain_yy = float(np.mean(np.abs(strain_yy)))
        mean_shear = float(np.mean(np.abs(shear)))

        # Principal strains at each point via eigenvalue formula for 2x2 symmetric tensor
        avg = 0.5 * (strain_xx + strain_yy)
        diff = 0.5 * (strain_xx - strain_yy)
        radius = np.sqrt(diff ** 2 + shear ** 2)
        principal_max = avg + radius
        max_principal = float(np.max(np.abs(principal_max)))

        # Overall deformation score (0-1), saturates at ~0.1 strain
        raw = (mean_strain_xx + mean_strain_yy + mean_shear) / 3.0
        deformation_score = float(np.clip(raw / 0.1, 0.0, 1.0))

        return {
            "strain_xx": round(mean_strain_xx, 6),
            "strain_yy": round(mean_strain_yy, 6),
            "shear_strain": round(mean_shear, 6),
            "max_principal_strain": round(max_principal, 6),
            "deformation_score": round(deformation_score, 4),
        }
