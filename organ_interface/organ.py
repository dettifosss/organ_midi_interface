from dataclasses import dataclass, field
from loguru import logger
from mido import Message as MidiMessage
import random

from yaml import safe_load as safe_load_yaml
from pathlib import Path
from typing import Optional, Iterator

from functools import total_ordering
from time import monotonic

from .note_attributes import NoteName, NoteAction, get_note_name, note_name_range
from .helpers import clamp_int, clamp_float

MAX_ACTIVATIONS: int = 5
CHANNEL_OFFSET: int = 1

@dataclass
class NoteEvent:
    note: "Note"
    action: NoteAction
    queued: bool=False
    sent: bool=False
    ts: float = field(default_factory=monotonic)
    channel: int=field(init=False)
    name: NoteName=field(init=False)
    note_state: "NoteState"=field(init=False)
    register: "Register"=field(init=False)
    midi_message: MidiMessage=field(init=False)

    def __post_init__(self) -> None:
        self.register = self.note.register
        self.channel = self.register.channel
        self.name = self.note.name
        self.note_state = self.note.state
        self._create_midi_message()

    def _create_midi_message(self) -> None:
        if self.action not in (NoteAction.PRESS, NoteAction.RELEASE):
            self.midi_message = None
            return
        if self.name == NoteName.NONE:
            self.midi_message = None
            return

        self.midi_message = MidiMessage(
                type = self.action.midi_message,
                note = self.name.value,
                velocity = 127,
                # NYI: Make sure this channel makes sense.
                channel = self.channel - CHANNEL_OFFSET # ChatGPT Claims there is some channel issues in mido
        )

    def midi_complete(self) -> None:
        logger.debug(f"MIDI completed for {self}")
        self.note_state.process_completed_event(self)

    def cancelled(self) -> None:
        logger.warning(f"Cancelled {self}")
        self.note_state.process_cancelled_event(self)

    def __repr__(self) -> str:
        return f"<NoteEvent: {self.action} for {self.name.pretty} on '{self.register.name}' over channel {self.channel}>"

class NoteState:
    def __init__(self, note: "Note", max_count: int=MAX_ACTIVATIONS) -> None:
        self._note: "Note" = note
        self._register: "Register" = note.register
        self._max_count: int = max_count
        self._actual_count: int = 0
        self._queued_count: int = 0

    @property
    def active(self) -> bool:
        return self._actual_count > 0 

    @property
    def queue_active(self) -> bool:
        return self._queued_count > 0 

    def process_action(self, action: NoteAction) -> NoteAction:
        logger.debug(f"Processing {action} for {self._note.name} on {self._register.name}, q_count={self._queued_count}, a_count={self._actual_count}")
        was_active: bool = self.queue_active
        self._queued_count = clamp_int(self._queued_count + action.delta, 0, self._max_count)
        if was_active != self.queue_active:
            logger.debug(f"-> Yielding {action}")
            return action
        #logger.debug(f"-> Yielding {NoteAction.NONE}")
        return NoteAction.NONE

    def process_completed_event(self, event: NoteEvent) -> None:
        logger.debug(f"Actual count updated for {self}:  {self._actual_count} -> {self._actual_count + event.action.delta}")
        self._actual_count = self._actual_count + event.action.delta

    def process_cancelled_event(self, event: NoteEvent) -> None:
        logger.debug(f"Queued count updated for {self}:  {self._queued_count} -> {self._queued_count - event.action.delta}")
        self._queued_count = clamp_int(self._queued_count - event.action.delta)

    def __repr__(self) -> str:
        return f"<NoteState {self._note.name.pretty:3} on '{self._register.name}': q_count = {self._queued_count}/{self._max_count}, count = {self._actual_count}/{self._max_count}>"

@total_ordering
class Note:
    def __init__(self, name: NoteName, register: "Register") -> None:
        self._name: NoteName = name
        self._register: "Register" = register
        self._channel: int = register.channel
        self._state: NoteState = NoteState(self)

    @property
    def name(self) -> NoteName:
        return self._name

    @property
    def register(self) -> "Register":
        return self._register
    
    @property
    def channel(self) -> int:
        return self._channel

    @property
    def state(self) -> NoteState:
        return self._state

    def get_note_event(self, action: NoteAction) -> NoteEvent:
        return NoteEvent(self, self._state.process_action(action))

    def __repr__(self) -> str:
        return f"<Note {self._name.pretty:3} on '{self._register.name}'>"

    def __lt__(self, other: "Note"):
        return self.name < other.name

    def __eq__(self, other: "Note"):
        return self.name == other.name

class Register:
    def __init__(
        self,
        name: str,
        channel: int,
        low_note_name: NoteName=NoteName.N36,
        high_note_name: NoteName=NoteName.N93
    ) -> None:
        self._name: str = name
        self._channel: int = channel
        self._notes: dict[NoteName, Note] = {nn: Note(nn, self) for nn in note_name_range(low_note_name, high_note_name)}

    @property
    def name(self) -> str:
        return self._name

    @property
    def channel(self) -> int:
        return self._channel

    @property
    def notes(self) -> list[Note]:
        return list(self._notes.values())

    @property
    def note_names(self) -> list[NoteName]:
        return list(self._notes.keys())

    @property
    def lowest_note(self) -> Note:
        return self._notes[self.lowest_note_name]

    @property
    def lowest_note_name(self) -> NoteName:
        return min(self._notes)

    @property
    def highest_note(self) -> Note:
        return self._notes[self.highest_note_name]

    @property
    def highest_note_name(self) -> NoteName:
        return max(self._notes)

    def __iter__(self) -> Iterator[Note]:
        return iter(self._notes.values())

    def __getitem__(self, note_name: NoteName) -> Note|None:
        return self._notes.get(note_name, None)

    def __repr__(self) -> str:
        return f"<Register: '{self._name}' [{self.lowest_note_name.pretty}, {self.highest_note_name.pretty}]>"

    def __len__(self) -> int:
        return len(self._notes)

class Organ:
    def __init__(self, config_file: Path):
        config = self.load_organ_config(config_file) # WARN: Type missing
        self._name: str = config.get("defaults", {}).get("name", "Generic")
        self._registers: dict[str, Register] = self.load_registers(config)

    @property
    def name(self) -> str:
        return self._name

    @property
    def registers(self) -> list[Register]:
        return list(self._registers.values())

    def load_organ_config(self, config_path: Path) -> dict[str, any]:
        with config_path.open("r", encoding="utf-8") as f:
            config = safe_load_yaml(f)
        return config

    def load_registers(self, config) -> dict[str, Register]:
        defaults: dict = config.get("defaults", {})
        d_low: int = defaults["note_range"]["low"]
        d_high: int = defaults["note_range"]["high"]
        d_max: int = defaults["max_activations"]

        registers: dict[str, Register] = {}

        for reg_cfg in config.get("registers", []):
            name: str = reg_cfg["name"]
            midi_channel: int = reg_cfg["midi"]["channel"]
            assert midi_channel in range(1, 17), f"Midi Channel, {midi_channel} is out of bounds [1,16]."
            max_activations: int = reg_cfg.get("max_activations", d_max)
            low_note_num: int = reg_cfg.get("note_range", {}).get("low", d_low)
            high_note_num: int = reg_cfg.get("note_range", {}).get("high", d_high)
            assert low_note_num < high_note_num, f"{low_note_num=} must be lower than {high_note_num}"
            _register: Register = Register(
                    name,
                    midi_channel,
                    low_note_name=get_note_name(low_note_num),
                    high_note_name=get_note_name(high_note_num)
                 )
            registers[name] = _register
        return registers

    def __iter__(self) -> Iterator[Register]:
        return iter(self._registers.values())

    def __getitem__(self, name:str) -> Register|None:
        try:
            return self._registers[name]
        except KeyError:
            logger.error(f"Register {name} does not exist in {self}")
            return None

    def __len__(self) -> int:
        return len(self._registers)

    def __repr__(self) -> str:
        return f"<Organ: {self._name} with {len(self._registers)} registers>"
