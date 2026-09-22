"""Simulation Engine — orchestrates simulation scenarios through the real pipeline."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from .scenarios import SCENARIOS

logger = logging.getLogger("splicetracker.simulation")


class SimulationEngine:
    def __init__(self, hardware_manager, intelligence_pipeline, event_bus, db_session_factory=None):
        self.hw = hardware_manager
        self.pipeline = intelligence_pipeline
        self.event_bus = event_bus
        self.db_session_factory = db_session_factory
        self.running = False
        self.current_scenario: Optional[str] = None
        self.current_step = 0
        self.total_steps = 0
        self.inspection_interval = 3.0
        self._task: Optional[asyncio.Task] = None
        self.results: list = []
        self.default_splice_id = "SP-003"

    async def start(self, scenario: str = "normal"):
        if self.running:
            await self.stop()
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}. Available: {list(SCENARIOS.keys())}")

        self.running = True
        self.current_scenario = scenario
        self.current_step = 0
        self.total_steps = SCENARIOS[scenario]["duration_steps"]
        self.results = []

        logger.info(f"Simulation started: {scenario} ({self.total_steps} steps)")
        if self.event_bus:
            await self.event_bus.publish("system_status", {
                "event": "simulation_started",
                "scenario": scenario,
                "total_steps": self.total_steps,
                "timestamp": datetime.utcnow().isoformat(),
            })

        self._task = asyncio.create_task(self._simulation_loop())

    async def stop(self):
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None

        logger.info("Simulation stopped")
        if self.event_bus:
            await self.event_bus.publish("system_status", {
                "event": "simulation_stopped",
                "scenario": self.current_scenario,
                "steps_completed": self.current_step,
                "timestamp": datetime.utcnow().isoformat(),
            })

    async def run_scenario(self, scenario_name: str) -> dict:
        await self.start(scenario_name)
        return {
            "status": "running",
            "scenario": scenario_name,
            "total_steps": self.total_steps,
            "description": SCENARIOS[scenario_name]["description"],
        }

    async def _simulation_loop(self):
        scenario = SCENARIOS[self.current_scenario]
        steps = scenario["steps"]

        try:
            for step_data in steps:
                if not self.running:
                    break

                self.current_step = step_data["step"]
                label = step_data.get("label", f"Step {self.current_step}")
                logger.info(f"Simulation step {self.current_step}/{self.total_steps}: {label}")

                await self._apply_scenario_step(step_data)
                result = await self._run_single_inspection(self.default_splice_id)
                self.results.append(result)

                if self.event_bus:
                    await self.event_bus.publish("inspection_completed", {
                        "splice_id": self.default_splice_id,
                        "step": self.current_step,
                        "total_steps": self.total_steps,
                        "label": label,
                        "result": result,
                        "timestamp": datetime.utcnow().isoformat(),
                    })

                if self.current_step < self.total_steps:
                    await asyncio.sleep(self.inspection_interval)

            logger.info(f"Simulation complete: {self.current_scenario}")
            if self.event_bus:
                await self.event_bus.publish("system_status", {
                    "event": "simulation_completed",
                    "scenario": self.current_scenario,
                    "steps_completed": self.current_step,
                    "timestamp": datetime.utcnow().isoformat(),
                })
        except asyncio.CancelledError:
            logger.info("Simulation cancelled")
        except Exception as e:
            logger.error(f"Simulation error: {e}")
        finally:
            self.running = False

    async def _apply_scenario_step(self, step_data: dict):
        vision_intensity = step_data.get("vision", 0.0)
        thermal_intensity = step_data.get("thermal", 0.0)
        mechanical_intensity = step_data.get("mechanical", 0.0)
        conductive_break = step_data.get("conductive", False)

        if self.hw:
            self.hw.set_anomaly("camera", vision_intensity > 0.1, vision_intensity)
            self.hw.set_anomaly("thermal", thermal_intensity > 0.1, thermal_intensity)
            self.hw.set_anomaly("mechanical", mechanical_intensity > 0.1, mechanical_intensity)
            if conductive_break:
                if hasattr(self.hw, "conductive") and self.hw.conductive:
                    self.hw.conductive.trigger_break()
            else:
                if hasattr(self.hw, "conductive") and self.hw.conductive:
                    self.hw.conductive.restore_continuity()

    async def _run_single_inspection(self, splice_id: str) -> dict:
        observations = {}

        if self.hw:
            observations = await self.hw.get_all_readings(splice_id)
        else:
            observations = self._generate_fallback_observations(splice_id)

        result = await self.pipeline.process_observations(splice_id, observations)
        return result

    def _generate_fallback_observations(self, splice_id: str) -> dict:
        step_data = SCENARIOS.get(self.current_scenario, {}).get("steps", [{}])
        idx = min(self.current_step - 1, len(step_data) - 1)
        step = step_data[idx] if idx >= 0 else {}

        return {
            "vision": {
                "anomaly_score": step.get("vision", 0.0),
                "confidence": 0.85,
                "available": True,
                "details": {"defect_type": "prototype_detection", "splice_detected": True},
            },
            "thermal": {
                "anomaly_score": step.get("thermal", 0.0),
                "confidence": 0.8,
                "available": True,
                "details": {"temperature": 36.7 + step.get("thermal", 0.0) * 20},
            },
            "mechanical": {
                "anomaly_score": step.get("mechanical", 0.0),
                "confidence": 0.8,
                "available": True,
                "details": {"rms": 0.1 + step.get("mechanical", 0.0) * 2.0},
            },
            "conductive": {
                "anomaly_score": 1.0 if step.get("conductive", False) else 0.0,
                "confidence": 0.95,
                "available": True,
                "details": {"continuity": not step.get("conductive", False)},
            },
        }

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "scenario": self.current_scenario,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "results_count": len(self.results),
            "available_scenarios": {
                k: {"name": v["name"], "description": v["description"], "duration_steps": v["duration_steps"]}
                for k, v in SCENARIOS.items()
            },
        }
