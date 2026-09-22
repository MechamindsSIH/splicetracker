"""Signal processing layer for SpliceTracker.

Provides sensor-specific processors and a synchroniser that aligns
observations from multiple sensor modalities within a time window.
"""

from .mechanical_processor import MechanicalProcessor
from .signal_sync import SignalSynchronizer
from .thermal_processor import ThermalProcessor
from .vision import VisionProcessor

__all__ = [
    "VisionProcessor",
    "ThermalProcessor",
    "MechanicalProcessor",
    "SignalSynchronizer",
]
