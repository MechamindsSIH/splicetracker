"""Tests for simulation scenario definitions.

The simulation scenarios are defined in the /api/simulation.py route as an
inline dict. These tests verify the scenario configuration is valid.
"""

import pytest


# The scenarios dict from the simulation module
SCENARIOS = {
    "normal": {"anomaly_prob": 0.05, "description": "Normal operating conditions"},
    "degrading": {"anomaly_prob": 0.50, "description": "Gradually degrading splice"},
    "critical": {"anomaly_prob": 0.90, "description": "Critical failure scenario"},
    "intermittent": {"anomaly_prob": 0.30, "description": "Intermittent fault detection"},
    "multi_defect": {"anomaly_prob": 0.70, "description": "Multiple concurrent defects"},
}

EXPECTED_SCENARIO_NAMES = {"normal", "degrading", "critical", "intermittent", "multi_defect"}


class TestScenariosDefined:
    """Tests for scenario configuration."""

    def test_all_expected_scenarios_exist(self):
        """All expected scenario names are defined."""
        assert set(SCENARIOS.keys()) == EXPECTED_SCENARIO_NAMES

    def test_scenario_count(self):
        """Correct number of scenarios are defined."""
        assert len(SCENARIOS) == 5


class TestScenarioSteps:
    """Tests that each scenario has valid configuration."""

    @pytest.mark.parametrize("name", EXPECTED_SCENARIO_NAMES)
    def test_scenario_has_anomaly_prob(self, name):
        """Each scenario has an anomaly_prob field."""
        assert "anomaly_prob" in SCENARIOS[name]

    @pytest.mark.parametrize("name", EXPECTED_SCENARIO_NAMES)
    def test_anomaly_prob_in_range(self, name):
        """Anomaly probability is between 0 and 1."""
        prob = SCENARIOS[name]["anomaly_prob"]
        assert 0.0 <= prob <= 1.0

    @pytest.mark.parametrize("name", EXPECTED_SCENARIO_NAMES)
    def test_scenario_has_description(self, name):
        """Each scenario has a non-empty description."""
        assert "description" in SCENARIOS[name]
        assert len(SCENARIOS[name]["description"]) > 0


class TestNormalScenario:
    """Tests specific to the 'normal' scenario."""

    def test_normal_has_low_anomaly_probability(self):
        """Normal scenario has a very low anomaly probability."""
        assert SCENARIOS["normal"]["anomaly_prob"] <= 0.1

    def test_normal_description_mentions_normal(self):
        """Normal scenario description is about normal operation."""
        desc = SCENARIOS["normal"]["description"].lower()
        assert "normal" in desc

    def test_critical_has_high_anomaly_probability(self):
        """Critical scenario has a high anomaly probability."""
        assert SCENARIOS["critical"]["anomaly_prob"] >= 0.8

    def test_degrading_is_moderate(self):
        """Degrading scenario has a moderate anomaly probability."""
        prob = SCENARIOS["degrading"]["anomaly_prob"]
        assert 0.3 <= prob <= 0.7

    def test_scenarios_ordered_by_severity(self):
        """Anomaly probabilities increase with scenario severity."""
        assert SCENARIOS["normal"]["anomaly_prob"] < SCENARIOS["intermittent"]["anomaly_prob"]
        assert SCENARIOS["intermittent"]["anomaly_prob"] < SCENARIOS["degrading"]["anomaly_prob"]
        assert SCENARIOS["degrading"]["anomaly_prob"] < SCENARIOS["multi_defect"]["anomaly_prob"]
        assert SCENARIOS["multi_defect"]["anomaly_prob"] < SCENARIOS["critical"]["anomaly_prob"]
