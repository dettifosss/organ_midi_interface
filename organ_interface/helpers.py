from loguru import logger

from mido import Message as MidiMessage
from mido.ports import BaseOutput

# HELPERS
def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))

def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
