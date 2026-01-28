from loguru import logger
from enum import Enum

from typing import Iterator


class NoteAction(Enum):
    PRESS = ("note_on", 1)
    RELEASE = ("note_off", -1)
    NONE = ("", 0)

    def __init__(self, midi_message: str, delta: int) -> None:
        self.midi_message = midi_message
        self.delta = delta

############################
# Create the NoteName Enum #
############################

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

#MIN_MIDI_NOTE: int = 36
#MAX_MIDI_NOTE: int = 93
MIN_MIDI_NOTE: int = 0
MAX_MIDI_NOTE: int = 127

def midi_note_name(number: int) -> str:
    if number == -1:
        return "No Note"
    octave = (number // 12) - 1
    name = _NOTE_NAMES[number % 12]
    return f"{name}{octave}"

# Build dict of member_name -> value
members = {"NONE": -1}
members.update({f"N{n}": n for n in range(MIN_MIDI_NOTE, MAX_MIDI_NOTE + 1)})

# Create the enum
NoteName = Enum("NoteName", members)

# Attach extra attributes
for member in NoteName:
    member.number = member.value
    member.pretty = midi_note_name(member.value)

NoteName.__lt__ = lambda self, other: self.value < other.value
NoteName.__eq__ = lambda self, other: self.value == other.value
NoteName.__le__ = lambda self, other: self.value <= other.value
NoteName.__gt__ = lambda self, other: self.value > other.value
NoteName.__ge__ = lambda self, other: self.value >= other.value

def get_note_name(number: int) -> NoteName:
    return NoteName[f"N{number}"]

def note_name_rangeUP(start: NoteName, end: NoteName) -> Iterator[NoteName]:
    if start.value > end.value:
        raise ValueError(f"Start note {start} must be <= end note {end}")
    for n in range(start.value, end.value + 1):
        try:
            yield get_note_name(n)
        except ValueError:
            continue

def note_name_range(start: NoteName, end: NoteName) -> Iterator[NoteName]:
    if start == end:
        logger.warning("Start and end notes are the same.")
        yield get_note_name(start.value)

        #logger.warning("Notes were the same, yielding a full Pedal range.")
        #start = NoteName.N36
        #end = NoteName.N67

    step: int
    if end < start:
        step = -1
    else:
        step = 1

    for n in range(start.value, end.value + step, step):
        try:
            yield get_note_name(n)
        except ValueError:
            continue

def get_note_subset(all_notes: list[NoteName], include: list[str]) -> list[NoteName]:
        #all_notes: list[NoteName] = [note for note in NoteName if note != NoteName.NONE]
        return [note for note in all_notes if note.pretty.rstrip("0123456789") in include]

############################
############################
############################