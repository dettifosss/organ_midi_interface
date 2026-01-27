from loguru import logger

from mido import Message as MidiMessage
from mido.ports import BaseOutput

from pathlib import Path
from yaml import safe_load as safe_load_yaml

import inspect

# HELPERS
def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))

def clamp_float(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

def load_config(config_path: Path) -> dict[str, any]:
    with config_path.open("r", encoding="utf-8") as f:
        config = safe_load_yaml(f)
    return config

def get_full_path(file: str) -> Path:
    caller_frame = inspect.stack()[1]
    caller_file = caller_frame.filename
    return Path(caller_file).resolve().parent / file
