"""Hardware Abstraction Layer for SpliceTracker.

Provides unified interfaces for camera, thermal, conductive, mechanical,
and belt-position sensors, with simulation and real hardware providers.
"""

from .camera import (
    CameraProvider,
    FrameBuffer,
    SimulationCameraProvider,
    USBWebcamProvider,
)
from .thermal import (
    ThermalProvider,
    SimulationThermalProvider,
    RealThermalProvider,
)
from .conductive import (
    ConductiveProvider,
    SimulationConductiveProvider,
    RealConductiveProvider,
)
from .mechanical import (
    MechanicalProvider,
    SimulationMechanicalProvider,
    RealMechanicalProvider,
)
from .belt_position import (
    BeltPositionProvider,
    SimulationBeltPositionProvider,
    EncoderBeltPositionProvider,
)
from .hardware_manager import HardwareManager

__all__ = [
    "CameraProvider",
    "FrameBuffer",
    "SimulationCameraProvider",
    "USBWebcamProvider",
    "ThermalProvider",
    "SimulationThermalProvider",
    "RealThermalProvider",
    "ConductiveProvider",
    "SimulationConductiveProvider",
    "RealConductiveProvider",
    "MechanicalProvider",
    "SimulationMechanicalProvider",
    "RealMechanicalProvider",
    "BeltPositionProvider",
    "SimulationBeltPositionProvider",
    "EncoderBeltPositionProvider",
    "HardwareManager",
]
