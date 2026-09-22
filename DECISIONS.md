# SpliceTracker — Architectural Decisions

## D-001: SQLite as Database
**Decision**: Use SQLite via aiosqlite for the database.
**Reason**: Prototype simplicity — single-file database, zero configuration, no external server. Sufficient for prototype data volumes. SQLAlchemy ORM makes migration to PostgreSQL straightforward if needed.

## D-002: FastAPI as Backend Framework
**Decision**: Use FastAPI with async handlers.
**Reason**: Native async support (critical for sensor polling and WebSocket), automatic OpenAPI documentation, Pydantic validation, excellent performance. Mature ecosystem.

## D-003: React + TypeScript + Vite + Tailwind CSS
**Decision**: Use React 18 with TypeScript, Vite bundler, and Tailwind CSS.
**Reason**: TypeScript provides type safety for complex data structures. Vite provides fast development experience. Tailwind enables rapid UI development with consistent styling. React is the most widely supported frontend framework.

## D-004: Provider Pattern for Hardware Abstraction
**Decision**: Abstract base class per sensor type with SimulationProvider and RealProvider implementations.
**Reason**: Intelligence pipeline must not care whether data comes from real hardware or simulation. Provider pattern allows hot-swapping, testing without hardware, and independent sensor development.

## D-005: Dict-Based Inter-Module Communication
**Decision**: Intelligence pipeline modules communicate via plain Python dicts, not direct imports of each other's internal types.
**Reason**: Loose coupling. Each engine (fusion, DIVE, ATCE, twin, risk) can be tested independently. Modules can be replaced without breaking consumers.

## D-006: AsyncIO Event Bus
**Decision**: Internal pub/sub event bus using asyncio for real-time event distribution.
**Reason**: Decouples event producers (sensors, intelligence) from consumers (WebSocket, logging, database). Enables real-time dashboard updates without polling.

## D-007: DIVE Naming
**Decision**: DIVE = Defect Intelligence and Validation Engine
**Reason**: Descriptive name for the event grouping and persistence tracking layer. Groups raw observations into meaningful events, classifies them, and validates through persistence.

## D-008: ATCE Naming
**Decision**: ATCE = Adaptive Temporal Correlation Engine
**Reason**: Descriptive name for the temporal pattern analysis layer. Correlates current events with history to detect trends, recurrence, and temporal patterns.

## D-009: Risk Scoring Approach
**Decision**: Weighted factor-based scoring (0-100) with named contributing factors.
**Reason**: Explainable risk assessment. Each factor (thermal anomaly, mechanical anomaly, etc.) has a defined weight. The operator can see exactly why risk is high. No black-box scoring.

## D-010: Sensor Fusion Weighting
**Decision**: Vision 30%, Thermal 25%, Mechanical 25%, Conductive 20% with agreement bonus.
**Reason**: Vision provides the richest information. Thermal and mechanical provide complementary physical measurements. Conductive is binary (break/no-break) so has lower continuous weight but high significance when triggered. Agreement between multiple sensors increases overall confidence.

## D-011: Condition State Machine
**Decision**: NORMAL → MINOR_ANOMALY → WARNING → DEGRADING → HIGH_RISK → CRITICAL with single-step transitions per inspection (unless confidence > 0.95).
**Reason**: Prevents sudden jumps from NORMAL to CRITICAL on a single noisy reading. Requires sustained evidence for severe conditions. Exception for overwhelming evidence prevents dangerous under-reaction.

## D-012: Alert Thresholds
**Decision**: WARNING at risk score 30, HIGH at 60, CRITICAL at 85.
**Reason**: LOW (0-29) represents normal/minor fluctuations that don't warrant operator attention. WARNING (30-59) signals developing issues. HIGH (60-84) requires attention. CRITICAL (85-100) demands immediate action.

## D-013: Event ID Format
**Decision**: EVT-XXXXXX (zero-padded 6-digit counter).
**Reason**: Human-readable, unique within session, consistent across all layers (database, log, WebSocket, dashboard). Easy to communicate verbally.

## D-014: Frame Storage Strategy
**Decision**: RAM ring buffer with event-triggered persistence to disk. Only store frames around events, not continuous recording.
**Reason**: Continuous frame storage is impractical for prototype. Event-driven capture preserves evidence while managing storage. Database stores paths, not image data.

## D-015: Simulation Through Backend
**Decision**: Simulation uses the same processing path as real hardware wherever practical.
**Reason**: Validates the actual intelligence pipeline, not a fake shortcut. Simulation providers inject data at the hardware abstraction boundary; everything downstream is identical.

## D-016: WebSocket for Real-Time Updates
**Decision**: WebSocket at /ws/live for pushing events to dashboard.
**Reason**: Eliminates polling latency. Dashboard receives events as they occur. Typed event schemas ensure frontend type safety. Auto-reconnect handles transient disconnections.

## D-017: No Authentication for Prototype
**Decision**: No authentication or authorization in the prototype.
**Reason**: Industrial prototype intended for local network demonstration. Adding auth adds complexity without prototype value. Production deployment would require proper auth.
