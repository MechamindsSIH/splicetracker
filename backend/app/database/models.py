"""SQLAlchemy ORM models for the SpliceTracker database."""

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── Enums ──────────────────────────────────────────────────────────────────

class SensorType(str, enum.Enum):
    VISION = "VISION"
    THERMAL = "THERMAL"
    CONDUCTIVE = "CONDUCTIVE"
    MECHANICAL = "MECHANICAL"


class SpliceCondition(str, enum.Enum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    DEGRADED = "DEGRADED"
    POOR = "POOR"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class InspectionStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AlertSeverity(str, enum.Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class FusionStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    CONFLICT = "CONFLICT"


class DIVEEventType(str, enum.Enum):
    DETECTION = "DETECTION"
    INFERENCE = "INFERENCE"
    VALIDATION = "VALIDATION"
    ESCALATION = "ESCALATION"


class DIVEStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"
    ESCALATED = "ESCALATED"


class ATCETrend(str, enum.Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    RAPID_DEGRADATION = "RAPID_DEGRADATION"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SystemEventSeverity(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ── Models ─────────────────────────────────────────────────────────────────

class Splice(Base):
    __tablename__ = "splices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, unique=True)
    belt_id = Column(String(64), nullable=False, index=True)
    position = Column(Float, nullable=False)
    installed_date = Column(DateTime, nullable=True)
    condition = Column(Enum(SpliceCondition), default=SpliceCondition.UNKNOWN, nullable=False)
    severity = Column(Float, default=0.0, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    inspections = relationship("Inspection", back_populates="splice", cascade="all, delete-orphan")
    sensor_measurements = relationship("SensorMeasurement", back_populates="splice", cascade="all, delete-orphan")
    vision_events = relationship("VisionEvent", back_populates="splice", cascade="all, delete-orphan")
    thermal_events = relationship("ThermalEvent", back_populates="splice", cascade="all, delete-orphan")
    conductive_events = relationship("ConductiveEvent", back_populates="splice", cascade="all, delete-orphan")
    mechanical_events = relationship("MechanicalEvent", back_populates="splice", cascade="all, delete-orphan")
    fusion_results = relationship("FusionResult", back_populates="splice", cascade="all, delete-orphan")
    dive_events = relationship("DIVEEvent", back_populates="splice", cascade="all, delete-orphan")
    atce_results = relationship("ATCEResult", back_populates="splice", cascade="all, delete-orphan")
    condition_history = relationship("ConditionHistory", back_populates="splice", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="splice", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_splices_belt_position", "belt_id", "position"),
        Index("ix_splices_condition", "condition"),
        Index("ix_splices_risk_level", "risk_level"),
    )


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)
    status = Column(Enum(InspectionStatus), default=InspectionStatus.PENDING, nullable=False)
    results_json = Column(Text, nullable=True)

    # Relationships
    splice = relationship("Splice", back_populates="inspections")
    sensor_measurements = relationship("SensorMeasurement", back_populates="inspection", cascade="all, delete-orphan")
    vision_events = relationship("VisionEvent", back_populates="inspection", cascade="all, delete-orphan")
    thermal_events = relationship("ThermalEvent", back_populates="inspection", cascade="all, delete-orphan")
    conductive_events = relationship("ConductiveEvent", back_populates="inspection", cascade="all, delete-orphan")
    mechanical_events = relationship("MechanicalEvent", back_populates="inspection", cascade="all, delete-orphan")
    fusion_results = relationship("FusionResult", back_populates="inspection", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_inspections_status", "status"),
        Index("ix_inspections_started_at", "started_at"),
    )


class SensorMeasurement(Base):
    __tablename__ = "sensor_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_type = Column(Enum(SensorType), nullable=False)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    value_json = Column(Text, nullable=True)
    anomaly_score = Column(Float, default=0.0, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    raw_value_json = Column(Text, nullable=True)

    # Relationships
    inspection = relationship("Inspection", back_populates="sensor_measurements")
    splice = relationship("Splice", back_populates="sensor_measurements")

    __table_args__ = (
        Index("ix_sensor_measurements_type_ts", "sensor_type", "timestamp"),
        Index("ix_sensor_measurements_splice_type", "splice_id", "sensor_type"),
    )


class VisionEvent(Base):
    __tablename__ = "vision_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    frame_path = Column(String(512), nullable=True)
    roi_json = Column(Text, nullable=True)
    defect_type = Column(String(64), nullable=True)
    defect_confidence = Column(Float, default=0.0, nullable=False)
    bounding_region_json = Column(Text, nullable=True)
    optical_flow_json = Column(Text, nullable=True)
    deformation_json = Column(Text, nullable=True)
    anomaly_score = Column(Float, default=0.0, nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="vision_events")
    splice = relationship("Splice", back_populates="vision_events")

    __table_args__ = (
        Index("ix_vision_events_ts", "timestamp"),
        Index("ix_vision_events_defect", "defect_type"),
    )


class ThermalEvent(Base):
    __tablename__ = "thermal_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    temperature = Column(Float, nullable=False)
    baseline_temperature = Column(Float, nullable=False)
    delta_temperature = Column(Float, nullable=False)
    rate_of_change = Column(Float, default=0.0, nullable=False)
    thermal_anomaly_score = Column(Float, default=0.0, nullable=False)
    hotspot_location_json = Column(Text, nullable=True)

    # Relationships
    inspection = relationship("Inspection", back_populates="thermal_events")
    splice = relationship("Splice", back_populates="thermal_events")

    __table_args__ = (
        Index("ix_thermal_events_ts", "timestamp"),
        Index("ix_thermal_events_anomaly", "thermal_anomaly_score"),
    )


class ConductiveEvent(Base):
    __tablename__ = "conductive_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    continuity = Column(Boolean, nullable=False)
    previous_state = Column(String(32), nullable=True)
    transition = Column(String(64), nullable=True)
    duration_ms = Column(Float, default=0.0, nullable=False)
    anomaly_score = Column(Float, default=0.0, nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="conductive_events")
    splice = relationship("Splice", back_populates="conductive_events")

    __table_args__ = (
        Index("ix_conductive_events_ts", "timestamp"),
        Index("ix_conductive_events_continuity", "continuity"),
    )


class MechanicalEvent(Base):
    __tablename__ = "mechanical_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    rms = Column(Float, nullable=False)
    peak = Column(Float, nullable=False)
    variance = Column(Float, nullable=False)
    frequency_features_json = Column(Text, nullable=True)
    anomaly_score = Column(Float, default=0.0, nullable=False)

    # Relationships
    inspection = relationship("Inspection", back_populates="mechanical_events")
    splice = relationship("Splice", back_populates="mechanical_events")

    __table_args__ = (
        Index("ix_mechanical_events_ts", "timestamp"),
        Index("ix_mechanical_events_anomaly", "anomaly_score"),
    )


class FusionResult(Base):
    __tablename__ = "fusion_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inspection_id = Column(Integer, ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    vision_score = Column(Float, default=0.0, nullable=False)
    thermal_score = Column(Float, default=0.0, nullable=False)
    mechanical_score = Column(Float, default=0.0, nullable=False)
    conductive_score = Column(Float, default=0.0, nullable=False)
    supporting_sensors = Column(Text, nullable=True)
    contradicting_sensors = Column(Text, nullable=True)
    overall_confidence = Column(Float, default=0.0, nullable=False)
    fusion_status = Column(Enum(FusionStatus), default=FusionStatus.PENDING, nullable=False)
    evidence_json = Column(Text, nullable=True)

    # Relationships
    inspection = relationship("Inspection", back_populates="fusion_results")
    splice = relationship("Splice", back_populates="fusion_results")
    dive_events = relationship("DIVEEvent", back_populates="fusion_result", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_fusion_results_ts", "timestamp"),
        Index("ix_fusion_results_status", "fusion_status"),
    )


class DIVEEvent(Base):
    __tablename__ = "dive_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    fusion_result_id = Column(Integer, ForeignKey("fusion_results.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(Enum(DIVEEventType), nullable=False)
    evidence_json = Column(Text, nullable=True)
    supporting_sensors_json = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    persistence_count = Column(Integer, default=0, nullable=False)
    status = Column(Enum(DIVEStatus), default=DIVEStatus.ACTIVE, nullable=False)

    # Relationships
    fusion_result = relationship("FusionResult", back_populates="dive_events")
    splice = relationship("Splice", back_populates="dive_events")
    atce_results = relationship("ATCEResult", back_populates="dive_event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_dive_events_type", "event_type"),
        Index("ix_dive_events_status", "status"),
    )


class ATCEResult(Base):
    __tablename__ = "atce_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dive_event_id = Column(Integer, ForeignKey("dive_events.id", ondelete="CASCADE"), nullable=False, index=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    previous_state = Column(String(32), nullable=True)
    current_state = Column(String(32), nullable=False)
    trend = Column(Enum(ATCETrend), nullable=False)
    persistence = Column(Integer, default=0, nullable=False)
    recurrence = Column(Boolean, default=False, nullable=False)
    history_json = Column(Text, nullable=True)

    # Relationships
    dive_event = relationship("DIVEEvent", back_populates="atce_results")
    splice = relationship("Splice", back_populates="atce_results")

    __table_args__ = (
        Index("ix_atce_results_ts", "timestamp"),
        Index("ix_atce_results_trend", "trend"),
    )


class ConditionHistory(Base):
    __tablename__ = "condition_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    condition = Column(Enum(SpliceCondition), nullable=False)
    severity = Column(Float, default=0.0, nullable=False)
    confidence = Column(Float, default=0.0, nullable=False)
    risk_level = Column(Enum(RiskLevel), default=RiskLevel.LOW, nullable=False)
    trigger_event_id = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    splice = relationship("Splice", back_populates="condition_history")

    __table_args__ = (
        Index("ix_condition_history_ts", "timestamp"),
        Index("ix_condition_history_splice_ts", "splice_id", "timestamp"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    splice_id = Column(Integer, ForeignKey("splices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    severity = Column(Enum(AlertSeverity), nullable=False)
    defect_type = Column(String(64), nullable=True)
    confidence = Column(Float, default=0.0, nullable=False)
    risk_score = Column(Float, default=0.0, nullable=False)
    reason = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    status = Column(Enum(AlertStatus), default=AlertStatus.ACTIVE, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(128), nullable=True)
    location = Column(String(128), nullable=True)

    # Relationships
    splice = relationship("Splice", back_populates="alerts")

    __table_args__ = (
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_ts", "timestamp"),
        Index("ix_alerts_splice_status", "splice_id", "status"),
    )


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, server_default=func.now(), nullable=False)
    event_type = Column(String(64), nullable=False, index=True)
    module = Column(String(128), nullable=False)
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    severity = Column(Enum(SystemEventSeverity), default=SystemEventSeverity.INFO, nullable=False)

    __table_args__ = (
        Index("ix_system_events_ts", "timestamp"),
        Index("ix_system_events_type_ts", "event_type", "timestamp"),
        Index("ix_system_events_severity", "severity"),
    )
