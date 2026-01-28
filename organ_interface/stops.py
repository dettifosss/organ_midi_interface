#from .organ import Organ, Register, NoteEvent, NoteState
from .note_attributes import NoteName, NoteEvent

HALLGRIMSKIRKJA_STOP_CHANNEL: int = 14

from dataclasses import dataclass, field

@dataclass
class HallgrimskirkjaStopEvent(NoteEvent):
	def __post_init__(self) -> None:
		super().__post_init__()
		self.channel = HALLGRIMSKIRKJA_STOP_CHANNEL

StopEvent = HallgrimskirkjaStopEvent

@dataclass
class Stop:
	name: str
	number: int
	size: int|None
	duplicates: bool
	note_name: NoteName=field(init=False)

	def __post_init__(self) -> None:
		self.note_name = NoteName[f"N{self.number}"]