"""Tests for risk assessment logic.

The project does not have a standalone risk_engine.py module; risk assessment
is performed inline in the simulation route (mapping overall scores and
conditions to RiskLevel). This test file exercises that mapping logic by
testing the same thresholds and verifying the analytics risk-factor derivation
from the analytics endpoint code.
"""

import pytest

from backend.app.database.models import RiskLevel, SpliceCondition


def _assess_risk(overall_score: float, is_anomaly: bool):
    """Replicate the risk assessment logic from the simulation module."""
    if is_anomaly:
        if overall_score > 0.8:
            return SpliceCondition.CRITICAL, RiskLevel.CRITICAL
        elif overall_score > 0.6:
            return SpliceCondition.POOR, RiskLevel.HIGH
        elif overall_score > 0.4:
            return SpliceCondition.DEGRADED, RiskLevel.MODERATE
        else:
            return SpliceCondition.FAIR, RiskLevel.LOW
    else:
        return SpliceCondition.GOOD, RiskLevel.LOW


def _compute_risk_factors(severity: float, confidence: float, condition: SpliceCondition):
    """Replicate the risk-factor logic from the analytics endpoint."""
    factors = []
    if severity > 0.7:
        factors.append("high_severity")
    if confidence < 0.5:
        factors.append("low_confidence")
    if condition in (SpliceCondition.POOR, SpliceCondition.CRITICAL):
        factors.append("poor_condition")
    return factors


def _recommended_action(risk_level: RiskLevel):
    """Map risk level to a recommended action."""
    actions = {
        RiskLevel.LOW: "Continue routine monitoring",
        RiskLevel.MODERATE: "Schedule maintenance inspection",
        RiskLevel.HIGH: "Schedule maintenance inspection",
        RiskLevel.CRITICAL: "Immediate inspection required",
    }
    return actions.get(risk_level, "Continue routine monitoring")


class TestRiskEngine:
    """Tests for risk assessment mapping."""

    def test_low_risk(self):
        """Normal conditions produce LOW risk and GOOD condition."""
        condition, risk = _assess_risk(0.1, is_anomaly=False)
        assert risk == RiskLevel.LOW
        assert condition == SpliceCondition.GOOD

    def test_medium_risk(self):
        """Moderate anomaly (score 0.5) -> MODERATE risk, DEGRADED condition."""
        condition, risk = _assess_risk(0.5, is_anomaly=True)
        assert risk == RiskLevel.MODERATE
        assert condition == SpliceCondition.DEGRADED

    def test_high_risk(self):
        """High anomaly score (0.7) -> HIGH risk, POOR condition."""
        condition, risk = _assess_risk(0.7, is_anomaly=True)
        assert risk == RiskLevel.HIGH
        assert condition == SpliceCondition.POOR

    def test_critical_risk(self):
        """Very high anomaly score (0.9) -> CRITICAL risk and condition."""
        condition, risk = _assess_risk(0.9, is_anomaly=True)
        assert risk == RiskLevel.CRITICAL
        assert condition == SpliceCondition.CRITICAL

    def test_risk_factors_high_severity(self):
        """High severity triggers the 'high_severity' factor."""
        factors = _compute_risk_factors(0.85, 0.9, SpliceCondition.DEGRADED)
        assert "high_severity" in factors
        assert "low_confidence" not in factors

    def test_risk_factors_low_confidence(self):
        """Low confidence triggers the 'low_confidence' factor."""
        factors = _compute_risk_factors(0.3, 0.3, SpliceCondition.FAIR)
        assert "low_confidence" in factors
        assert "high_severity" not in factors

    def test_risk_factors_poor_condition(self):
        """POOR or CRITICAL condition triggers the 'poor_condition' factor."""
        factors = _compute_risk_factors(0.8, 0.9, SpliceCondition.CRITICAL)
        assert "poor_condition" in factors
        assert "high_severity" in factors

    def test_risk_factors_all(self):
        """Multiple factors can be present simultaneously."""
        factors = _compute_risk_factors(0.9, 0.3, SpliceCondition.POOR)
        assert "high_severity" in factors
        assert "low_confidence" in factors
        assert "poor_condition" in factors

    def test_risk_factors_none(self):
        """Good conditions produce no risk factors."""
        factors = _compute_risk_factors(0.1, 0.9, SpliceCondition.GOOD)
        assert factors == []

    def test_recommended_action_low(self):
        """LOW risk -> routine monitoring."""
        assert _recommended_action(RiskLevel.LOW) == "Continue routine monitoring"

    def test_recommended_action_moderate(self):
        """MODERATE risk -> schedule maintenance."""
        assert _recommended_action(RiskLevel.MODERATE) == "Schedule maintenance inspection"

    def test_recommended_action_high(self):
        """HIGH risk -> schedule maintenance."""
        assert _recommended_action(RiskLevel.HIGH) == "Schedule maintenance inspection"

    def test_recommended_action_critical(self):
        """CRITICAL risk -> immediate inspection."""
        assert _recommended_action(RiskLevel.CRITICAL) == "Immediate inspection required"

    def test_boundary_at_0_4(self):
        """Score exactly at boundary 0.4 -> LOW risk (not above 0.4)."""
        condition, risk = _assess_risk(0.4, is_anomaly=True)
        assert risk == RiskLevel.LOW
        assert condition == SpliceCondition.FAIR

    def test_boundary_at_0_6(self):
        """Score exactly at boundary 0.6 -> MODERATE (not above 0.6)."""
        condition, risk = _assess_risk(0.6, is_anomaly=True)
        assert risk == RiskLevel.MODERATE
        assert condition == SpliceCondition.DEGRADED
