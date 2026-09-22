# SpliceTracker — Hardware Interface Guide

## Architecture

Every sensor type uses the Provider pattern:

```
SensorProvider (Abstract Base)
├── SimulationProvider (built-in)
└── RealProvider (implement per hardware)
```

The intelligence pipeline is hardware-agnostic. HardwareManager initializes providers based on configuration.

## Camera

**Interface**: `CameraProvider`
**File**: `backend/app/hardware/camera.py`

### SimulationCameraProvider
- Generates synthetic belt frames with configurable anomalies
- Modes: crack, deformation, discoloration, edge_damage

### USBWebcamProvider
- Uses OpenCV `cv2.VideoCapture`
- Config: `CAMERA_INDEX` (default 0), `CAMERA_WIDTH`, `CAMERA_HEIGHT`, `CAMERA_FPS`
- Connect: USB webcam to host computer

### Frame Buffer
- Ring buffer in RAM (`FRAME_BUFFER_SIZE` frames)
- Event-triggered persistence: captures pre/post event frames
- Saves to `data/frames/` directory

## Thermal Sensor

**Interface**: `ThermalProvider`
**File**: `backend/app/hardware/thermal.py`

### SimulationThermalProvider
- Baseline: 36.7C with configurable noise
- Anomaly injection: raises temperature proportional to intensity

### RealThermalProvider (template)
- Serial/USB connection
- Config: port, baudrate (9600)
- Protocol: reads temperature float from serial line
- Compatible sensors: MLX90614, AMG8833, or similar

### Wiring
```
Thermal Sensor -> USB/Serial Adapter -> Host
                  or I2C -> Raspberry Pi GPIO
```

## Conductive Sensor

**Interface**: `ConductiveProvider`
**File**: `backend/app/hardware/conductive.py`

### SimulationConductiveProvider
- Binary continuity state (true/false)
- Break/restore functions for testing

### RealConductiveProvider (template)
- GPIO digital input or serial
- Reads continuity loop status
- Config: port, baudrate

### Wiring
```
Conductive Loop -> GPIO Pin (normally HIGH)
                   Break = pin goes LOW
```

## Mechanical Sensor

**Interface**: `MechanicalProvider`
**File**: `backend/app/hardware/mechanical.py`

### SimulationMechanicalProvider
- Generates synthetic vibration signals
- Normal: low-amplitude noise
- Anomaly: adds periodic components + higher amplitude
- Computes real RMS, peak, variance, FFT features

### RealMechanicalProvider (template)
- Accelerometer via serial/USB/I2C
- Compatible: ADXL345, MPU6050, or industrial vibration sensor
- Config: port, baudrate, sample_rate

### Wiring
```
Accelerometer -> I2C/SPI -> Raspberry Pi / Arduino -> USB -> Host
```

## Belt Position

**Interface**: `BeltPositionProvider`
**File**: `backend/app/hardware/belt_position.py`

### SimulationBeltPositionProvider
- Speed * elapsed time estimation
- Configurable splice positions
- Config: `BELT_SPEED`, `BELT_LENGTH`

### EncoderBeltPositionProvider (template)
- Rotary encoder on belt roller
- Pulse counting for distance
- Config: pulses_per_revolution, roller_circumference

### Wiring
```
Rotary Encoder -> GPIO (A/B channels) -> Raspberry Pi
                  or Encoder -> Arduino -> USB -> Host
```

## Creating a New Real Provider

1. Subclass the abstract base (e.g., `CameraProvider`)
2. Implement all abstract methods: `start()`, `stop()`, `get_frame()`/`read()`, `is_connected()`
3. Register in `HardwareManager._init_*` method
4. Add config flag (e.g., `CAMERA_PROVIDER=usb`)
5. Test independently before integration
