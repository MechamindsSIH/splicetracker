"""Intelligence Pipeline — orchestrates the full processing chain."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from .sensor_fusion import SensorFusionEngine
from .dive_engine import DIVEEngine
from .atce_engine import ATCEEngine
from .temporal_twin import TemporalDigitalTwin
from .risk_engine import RiskEngine


@dataclass
class PipelineResult:
    splice_id: str
    timestamp: str = ""
    fusion_result: dict = field(default_factory=dict)
    dive_event: dict = field(default_factory=dict)
    atce_result: dict = field(default_factory=dict)
    twin_state: dict = field(default_factory=dict)
    risk_result: dict = field(default_factory=dict)
    alert: Optional[dict] = None
    pipeline_status: str = "completed"

    def to_dict(self) -> dict:
        return asdict(self)


class IntelligencePipeline:
    def __init__(self, event_bus=None, db_session_factory=None, config=None):
        self.fusion = SensorFusionEngine(config)
        self.dive = DIVEEngine()
        self.atce = ATCEEngine()
        self.twin = TemporalDigitalTwin()
        self.risk = RiskEngine()
        self.event_bus = event_bus
        self.db_session_factory = db_session_factory
        self.pipeline_stages = {}
        self._update_stage("Pipeline", "idle", "Waiting for observations")

    async def process_observations(
        self, splice_id: str, observations: dict
    ) -> dict:
        now = datetime.utcnow().isoformat()
        result = PipelineResult(splice_id=splice_id, timestamp=now)

        try:
            self._update_stage("Sensor Fusion", "processing", "Fusing sensor data")
            fusion = await self.fusion.fuse(observations)
            result.fusion_result = fusion
            self._update_stage(
                "Sensor Fusion", "completed", fusion.get("fusion_status", "UNKNOWN")
            )

            if self.event_bus:
                await self.event_bus.publish(
                    "fusion_updated",
                    {"splice_id": splice_id, "fusion": fusion, "timestamp": now},
                )

            self._update_stage("DIVE", "processing", "Processing event")
            dive_event = await self.dive.process(fusion, splice_id)
            result.dive_event = dive_event
            self._update_stage(
                "DIVE", "completed", dive_event.get("status", "UNKNOWN")
            )

            condition_history = self.twin.get_history(splice_id)
            self._update_stage("ATCE", "processing", "Analyzing temporal patterns")
            atce = await self.atce.analyze(dive_event, splice_id, condition_history)
            result.atce_result = atce
            self._update_stage(
                "ATCE", "completed", atce.get("trend", "UNKNOWN")
            )

            self._update_stage(
                "Temporal Twin", "processing", "Updating splice state"
            )
            twin_state = await self.twin.update(splice_id, atce, fusion)
            result.twin_state = twin_state
            self._update_stage(
                "Temporal Twin",
                "completed",
                twin_state.get("condition", "UNKNOWN"),
            )

            if self.event_bus:
                await self.event_bus.publish(
                    "condition_updated",
                    {
                        "splice_id": splice_id,
                        "condition": twin_state.get("condition"),
                        "severity": twin_state.get("severity"),
                        "timestamp": now,
                    },
                )

            self._update_stage("Risk Engine", "processing", "Evaluating risk")
            risk = await self.risk.evaluate(splice_id, fusion, atce, twin_state)
            result.risk_result = risk
            self._update_stage(
                "Risk Engine", "completed", risk.get("risk_level", "UNKNOWN")
            )

            twin_state_updated = await self.twin.update(
                splice_id, atce, fusion, risk
            )
            result.twin_state = twin_state_updated

            if self.event_bus:
                await self.event_bus.publish(
                    "risk_updated",
                    {
                        "splice_id": splice_id,
                        "risk_level": risk.get("risk_level"),
                        "risk_score": risk.get("risk_score"),
                        "timestamp": now,
                    },
                )

            result.pipeline_status = "completed"
            self._update_stage("Pipeline", "completed", "Processing complete")

        except Exception as e:
            result.pipeline_status = f"error: {str(e)}"
            self._update_stage("Pipeline", "error", str(e))

        return result.to_dict()

    def get_pipeline_status(self) -> list:
        return [
            {
                "name": name,
                "status": info.get("status", "idle"),
                "last_event": info.get("last_event", ""),
                "processing_result": info.get("result", ""),
                "error_state": info.get("error"),
            }
            for name, info in self.pipeline_stages.items()
        ]

    def get_twin(self) -> TemporalDigitalTwin:
        return self.twin

    def _update_stage(self, name: str, status: str, result: str = ""):
        self.pipeline_stages[name] = {
            "status": status,
            "last_event": datetime.utcnow().isoformat(),
            "result": result,
            "error": result if status == "error" else None,
        }
