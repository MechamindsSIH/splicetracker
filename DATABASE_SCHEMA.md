# SpliceTracker — Database Schema

Database Version: 1.0
Engine: SQLite via aiosqlite + SQLAlchemy 2.0

## Tables

### splices
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| name | VARCHAR(50) | NOT NULL, UNIQUE |
| belt_id | VARCHAR(50) | NOT NULL, DEFAULT 'B-01' |
| position | FLOAT | NOT NULL |
| installed_date | DATETIME | |
| condition | VARCHAR(20) | DEFAULT 'NORMAL' |
| severity | VARCHAR(20) | DEFAULT 'NONE' |
| confidence | FLOAT | DEFAULT 0.0 |
| risk_level | VARCHAR(20) | DEFAULT 'LOW' |
| created_at | DATETIME | NOT NULL, DEFAULT now |
| updated_at | DATETIME | NOT NULL, DEFAULT now |

### inspections
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| splice_id | INTEGER | FK -> splices.id, NOT NULL |
| started_at | DATETIME | NOT NULL |
| completed_at | DATETIME | |
| status | VARCHAR(20) | DEFAULT 'pending' |
| results_json | JSON | |

### sensor_measurements
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| inspection_id | INTEGER | FK -> inspections.id |
| splice_id | INTEGER | FK -> splices.id |
| sensor_type | VARCHAR(20) | NOT NULL (VISION/THERMAL/CONDUCTIVE/MECHANICAL) |
| timestamp | DATETIME | NOT NULL |
| value_json | JSON | |
| anomaly_score | FLOAT | DEFAULT 0.0 |
| confidence | FLOAT | DEFAULT 0.0 |
| raw_value_json | JSON | |

### vision_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| inspection_id | INTEGER | FK -> inspections.id |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| frame_path | VARCHAR(500) | |
| roi_json | JSON | |
| defect_type | VARCHAR(50) | |
| defect_confidence | FLOAT | DEFAULT 0.0 |
| bounding_region_json | JSON | |
| optical_flow_json | JSON | |
| deformation_json | JSON | |
| anomaly_score | FLOAT | DEFAULT 0.0 |

### thermal_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| inspection_id | INTEGER | FK -> inspections.id |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| temperature | FLOAT | |
| baseline_temperature | FLOAT | |
| delta_temperature | FLOAT | |
| rate_of_change | FLOAT | |
| thermal_anomaly_score | FLOAT | DEFAULT 0.0 |
| hotspot_location_json | JSON | |

### conductive_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| inspection_id | INTEGER | FK -> inspections.id |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| continuity | BOOLEAN | NOT NULL |
| previous_state | VARCHAR(20) | |
| transition | VARCHAR(50) | |
| duration_ms | FLOAT | |
| anomaly_score | FLOAT | DEFAULT 0.0 |

### mechanical_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| inspection_id | INTEGER | FK -> inspections.id |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| rms | FLOAT | |
| peak | FLOAT | |
| variance | FLOAT | |
| frequency_features_json | JSON | |
| anomaly_score | FLOAT | DEFAULT 0.0 |

### fusion_results
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| inspection_id | INTEGER | FK -> inspections.id |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| vision_score | FLOAT | DEFAULT 0.0 |
| thermal_score | FLOAT | DEFAULT 0.0 |
| mechanical_score | FLOAT | DEFAULT 0.0 |
| conductive_score | FLOAT | DEFAULT 0.0 |
| supporting_sensors | INTEGER | DEFAULT 0 |
| contradicting_sensors | INTEGER | DEFAULT 0 |
| overall_confidence | FLOAT | DEFAULT 0.0 |
| fusion_status | VARCHAR(30) | |
| evidence_json | JSON | |

### dive_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| fusion_result_id | INTEGER | FK -> fusion_results.id |
| splice_id | INTEGER | FK -> splices.id |
| event_type | VARCHAR(50) | |
| evidence_json | JSON | |
| supporting_sensors_json | JSON | |
| confidence | FLOAT | DEFAULT 0.0 |
| start_time | DATETIME | |
| end_time | DATETIME | |
| persistence_count | INTEGER | DEFAULT 0 |
| status | VARCHAR(20) | DEFAULT 'ACTIVE' |

### atce_results
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| dive_event_id | INTEGER | FK -> dive_events.id |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| previous_state | VARCHAR(20) | |
| current_state | VARCHAR(20) | |
| trend | VARCHAR(20) | |
| persistence | INTEGER | DEFAULT 0 |
| recurrence | BOOLEAN | DEFAULT false |
| history_json | JSON | |

### condition_history
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| splice_id | INTEGER | FK -> splices.id, NOT NULL |
| timestamp | DATETIME | NOT NULL |
| condition | VARCHAR(20) | NOT NULL |
| severity | VARCHAR(20) | |
| confidence | FLOAT | DEFAULT 0.0 |
| risk_level | VARCHAR(20) | |
| trigger_event_id | INTEGER | |
| notes | TEXT | |

### alerts
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| splice_id | INTEGER | FK -> splices.id |
| timestamp | DATETIME | NOT NULL |
| severity | VARCHAR(20) | NOT NULL |
| defect_type | VARCHAR(50) | |
| confidence | FLOAT | DEFAULT 0.0 |
| risk_score | FLOAT | DEFAULT 0.0 |
| reason | TEXT | |
| recommended_action | TEXT | |
| status | VARCHAR(20) | DEFAULT 'ACTIVE' |
| acknowledged_at | DATETIME | |
| acknowledged_by | VARCHAR(100) | |
| location | VARCHAR(100) | |

### system_events
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PK, autoincrement |
| timestamp | DATETIME | NOT NULL |
| event_type | VARCHAR(50) | NOT NULL |
| module | VARCHAR(50) | |
| message | TEXT | |
| details_json | JSON | |
| severity | VARCHAR(20) | DEFAULT 'INFO' |

## Indexes
- splices: name (unique)
- inspections: splice_id, started_at
- sensor_measurements: splice_id, sensor_type, timestamp
- alerts: splice_id, status, severity, timestamp
- condition_history: splice_id, timestamp
- system_events: event_type, timestamp

## Relationships
- Splice 1:N Inspections
- Splice 1:N ConditionHistory
- Splice 1:N Alerts
- Inspection 1:N SensorMeasurements
- Inspection 1:N VisionEvents, ThermalEvents, ConductiveEvents, MechanicalEvents
- Inspection 1:1 FusionResult
- FusionResult 1:1 DIVEEvent
- DIVEEvent 1:1 ATCEResult
