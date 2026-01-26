from loguru import logger
from typing import Iterator
import random
import time

from .organ import Organ, Register, Note, NoteEvent
from .note_attributes import NoteName, NoteAction, get_note_name, note_name_range, get_note_subset
from .helpers import clamp_float
from queue import Queue, Full

from abc import abstractmethod

MAX_PEDAL_VOICES = 6
MAX_VOICES = 12

class Voice:
	def __init__(self, voice_id: str, register: Register) -> None:

		self._id: str = voice_id
		self._register: Register = register

		self._voice_on: bool = False
		self._changed: bool = False

		self._notes: list[NoteName] = self.allowed_notes
		self._last_note: NoteName = self._notes[0]
		self._active_note: NoteName = self._notes[0]
		self._next_note: NoteName = self._notes[0]

		self._n_notes: int
		self.create_note_list(register.lowest_note_name, register.highest_note_name, reset=True)

	@abstractmethod
	def reset(self) -> None:
		pass

	def create_note_list(self, first_note: NoteName, last_note: NoteName, reset: bool=True) -> None:
		# should implement chords/scales here.
		self.notes = list(note_name_range(first_note, last_note))
		if reset:
			self.reset()

	def assign_random_range(self,
			include_notes: list[str]|None = None,
			keep_current: bool=True,
			reset: bool=True
			) -> None:

		# NB: Not sure if this is my intention.
		if include_notes is None:
			include_notes = ["C", "E", "G"]

		current_note: NoteName = self.active_note
		endpoints: list[NoteName] = []
		subset_notes: list[NoteName] = get_note_subset(self.allowed_notes, include_notes)
		
		if keep_current:
			try:
				subset_notes.remove(current_note)
			except ValueError:
				pass
			endpoints.append(current_note)
			endpoints.append(random.choice(subset_notes))
		else:
			endpoints = random.sample(subset_notes, 2)
		self.create_note_list(*endpoints, reset=reset)

	@property
	def name(self) -> str:
		return self._id

	@property
	def notes(self) -> list[NoteName]:
		return self._notes

	@notes.setter
	def notes(self, notes: list[NoteName]) -> None:
		self._notes = notes
		self._n_notes = len(notes)

	@property
	def next_note(self) -> NoteName:
		return self._next_note

	@next_note.setter
	def next_note(self, next_note: NoteName) -> None:
		if next_note != self._next_note:
			self._changed = True
		self._next_note = next_note

	@property
	def active_note(self) -> NoteName:
		return self._active_note

	@active_note.setter
	def active_note(self, next_note: NoteName) -> None:
		if next_note != self._active_note:
			self._changed = True
		self._last_note = self._active_note
		self._active_note = next_note

	@property
	def register(self) -> Register:
		return self._register

	@property
	def allowed_notes(self) -> list[NoteName]:
		return self._register.note_names

	def on(self) -> None:
		was: bool = self._voice_on
		self._voice_on = True
		if was != self._voice_on:
			self._changed = True

	def off(self) -> None:
		was: bool = self._voice_on
		self._voice_on = False
		if was != self._voice_on:
			self._changed = True

	def create_note_events(self) -> list[NoteEvent|None]:
		if not self._changed:
			return [None]
		if not self._voice_on:
			return [self._create_active_note_event(NoteAction.RELEASE)]

		note_events: list[NoteEvent] = []
		# BUG: This migt not work correctly between voices on startup.
		#      It might send too many RELEASE events.
		# I think it should be ok on the underlying method thoguh.
		# Maybe add a self._startup flag?

		note_events.append(self._create_active_note_event(NoteAction.RELEASE))
		self.active_note = self.next_note
		note_events.append(self._create_active_note_event(NoteAction.PRESS))
		self._changed = False
		
		return note_events

	def queue_midi(self, queue: Queue) -> None:
		note_events: list[NoteEvent] = self.create_note_events()
		if note_events is None:
			return
		for note_event in note_events:
			if note_event is None:
				continue
			if note_event.action == NoteAction.NONE:
				note_event.midi_complete()
				continue
			try:
				queue.put(note_event, block=False)
			except Full:
				note_event.cancelled()

	def _get_active_note(self) -> Note:
		return self._register[self.active_note]

	def _create_active_note_event(self, action: NoteAction) -> NoteEvent:
		return self._get_active_note().get_note_event(action)

	def __getitem__(self, num: int) -> NoteName:
		return self._notes[num]

	def __len__(self) -> int:
		return self._n_notes

	def __repr__(self) -> str:
	    return (
	        f"<{type(self).__name__} {' (ON)' if self._voice_on else '(OFF)'} "
	        f"{self._register.name}-{self._id} "
	        f"[{self._notes[0].pretty}, {self._notes[-1].pretty}] : "
	        f"{self._last_note.pretty} - {self.active_note.pretty} - {self.next_note.pretty}>"
	    )

class WebVoice(Voice):
	def reset(self) -> None:
		self.next_note = self._notes[0]
		self.active_note = self.next_note

	def get_note_num(self, note_name: NoteName) -> int:
		try: 
			return self._notes.index(note_name)
		except ValueError:
			return -1

	def set_note_num(self, num:int) -> None:
		if num < 0 or num >= len(self):
			logger.warning(f"Note index {num} out of range")
			return
		self.next_note = self._notes[num]

class RatioVoice(Voice):
	def __init__(self, voice_id: str, register: Register) -> None:
		self._ratio: float = 0.0
		self._ratio_multiplier:int
		super().__init__(voice_id, register)

	def reset(self) -> None:
		self.ratio = 0.0

	def create_note_list(self, first_note: NoteName, last_note: NoteName, reset: bool=True) -> None:
		super().create_note_list(first_note, last_note, reset=False)
		self._ratio_multiplier = max(len(self._notes) - 1, 1)
		self.reset()

	@property
	def ratio(self) -> float:
		return self._ratio

	@ratio.setter
	def ratio(self, value: float) -> None:
		self._ratio = clamp_float(value, 0.0, 1.0)
		self._ratio_to_note()

	def _ratio_to_note(self) -> None:
		index: int = round(self._ratio * self._ratio_multiplier)
		index = min(index, self._ratio_multiplier)
		self.next_note = self._notes[index]

class ComputerVoice(Voice):
	pass

class VoiceController:
	def __init__(self, vm: "VoiceManager", voice_cls: type[Voice]) -> None:
		self._vm = vm
		self._voice_cls = voice_cls

	@property
	def queue(self) -> Queue:
		return self._vm.queue

	def assign_random_ranges(self,
			include_notes: list[str]|None = None,
			keep_current: bool=True,
			reset: bool=True
			) -> None:
		for v in self:
			v.assign_random_range(include_notes, keep_current, reset)

	# def assign_random_ranges_old(self,
	# 		include_notes: list[str]|None = None,
	# 		keep_current: bool=True,
	# 		reset: bool=True
	# 		) -> None:

	# 	# NB: Not sure if this is my intention.
	# 	if include_notes is None:
	# 		include_notes = ["C", "E", "G"]

	# 	for v in self:
	# 		current_note: NoteName = v.active_note
	# 		endpoints: list[NoteName] = []
	# 		subset_notes: list[NoteName] = get_note_subset(v.allowed_notes, include_notes)
			
	# 		if keep_current:
	# 			try:
	# 				subset_notes.remove(current_note)
	# 			except ValueError:
	# 				pass
	# 			endpoints.append(current_note)
	# 			endpoints.append(random.choice(subset_notes))
	# 		else:
	# 			endpoints = random.sample(subset_notes, 2)
	# 		v.create_note_list(*endpoints, reset=reset)


	def queue_all_midi(self) -> None:
		for v in self:
			try:
				v.queue_midi(self.queue)
			except AttributeError as e:
				logger.error(e)
				for v in vm:
					logger.error(v)

	def all_on(self):
		for v in self:
			v.on()

	def all_off(self):
		for v in self:
			v.off()

	def cycle_notes(self) -> None:
		# NYI:
		# Also maybe this should be done down to voice level.
		pass

	def __len__(self) -> int:
		return len(list(self._vm.get_voices_by_class(self._voice_cls)))

	def __iter__(self) -> Iterator[Voice]:
		return iter(self._vm.get_voices_by_class(self._voice_cls))

	def __repr__(self) -> str:
		return f"<Voice Controller for {len(self)} {self._voice_cls.__name__}(s)>"

class RatioVoiceController(VoiceController):
	def set_all_voice_ratios(self, ratio: float=0.0, send_midi: bool=True) -> None:
		for v in self:
			v.ratio = ratio
			if send_midi:
				v.queue_midi(self.queue)

	def increment_all_voice_ratios(self, delta: float) -> None:
		for v in self:
			v.ratio += delta

	def cycle_notes(self, loop_time: float=0.01, steps: int=10000, timing:bool=False):
	    self.set_all_voice_ratios(0.0)
	    if timing:
	        times = []
	    for k in range(steps + 1):
	        loop_start = time.perf_counter()
	        self.increment_all_voice_ratios(1.0 / steps)
	        self.queue_all_midi()
	        
	        if timing:
	            times.append(time.perf_counter() - loop_start)
	        time.sleep(loop_time - (loop_start - time.perf_counter()))

	    if timing:
	        import numpy as np
	        print("max:", max(times)*1000, "ms")
	        print("avg:", np.mean(times)*1000, "ms")
	        print("99th percentile:", np.percentile(times, 99)*1000, "ms")

class WebVoiceController(VoiceController):
	def set_all_voice_nums(self, num: int) -> None:
		for v in self:
			if 0 <= num < len(v):
				v.set_note_num(num)

			
	def cycle_notes(self) -> None:
	    for k in range(40):
	        self.set_all_voice_nums(k)
	        self.queue_all_midi()
	        time.sleep(0.1)


class ComputerVoiceController(VoiceController):
	pass
	

class VoiceManager:
	def __init__(self, organ: Organ, queue: Queue) -> None:
		self._organ = organ
		self._queue: Queue = queue
		self._registers = organ.registers
		self._voices: dict[str, Voice] = {}
		self._voice_count: dict[Register, int] = {reg: 0 for reg in organ}
		self._voice_controllers: dict[type[Voice], VoiceController] = {}
		for voice_cls in Voice.__subclasses__():
		    controller_cls_name = voice_cls.__name__ + "Controller"
		    controller_cls = globals()[controller_cls_name]  # assumes controller class exists
		    self._voice_controllers[voice_cls] = controller_cls(self, voice_cls)

	@property
	def queue(self) -> Queue:
		return self._queue

	@property
	def voice_controllers(self) -> Iterator[VoiceController]:
		return self._voice_controllers.values()

	def register_full(self, register: Register) -> bool:
		max_per_voice: int = MAX_VOICES
		if register.name == "Pedal":
			max_per_voice = MAX_PEDAL_VOICES
		return self._voice_count[register] >= max_per_voice

	def create_random_voice(self, voice_id: str|None=None, voice_cls: type[Voice]=Voice) -> Voice|None:
		registers: list[Register] = [r for r in self._organ if not self.register_full(r)]
		if len(registers) <= 0:
			logger.error("All voices are ocupied.")
			return
		register: Register = random.choice(registers)
		if voice_id is None:
			voice_id = ''.join(random.choices('0123456789abcdef', k=10))
		return self.create_voice(voice_id, register, voice_cls)

	def create_random_voices(self, num: int, voice_cls: type[Voice]=Voice) -> None:
		for k in range(num):
			self.create_random_voice(voice_cls=voice_cls)

	def create_voice(self, voice_id: str, register: Register, voice_cls: type[Voice]=Voice) -> Voice:
		voice: Voice = voice_cls(voice_id, register)
		self._voices[voice_id] = voice
		self._voice_count[voice._register] += 1
		return voice

	def remove_voice(self, voice: Voice) -> None:
		self._voices.pop(voice.name)
		self._voice_count[voice.register] -= 1 # need to have a check here.

	def get_voice_controller(self, voice_cls: type[Voice]) -> VoiceController:
		return self._voice_controllers[voice_cls]

	def get_voices_by_class(self, voice_cls: type[Voice]) -> Iterator[type[Voice]]:
		return filter(lambda v: isinstance(v, voice_cls), self)

	def __getattr__(self, name):
		def dispatcher(*args, **kwargs):
			handled = False
			for vc in self.voice_controllers:
				if hasattr(vc, name):
					getattr(vc, name)(*args, **kwargs)
					handled = True
			if not handled:
				raise AttributeError(f"No controller has method {name}")
		return dispatcher

	def __getitem__(self, voice_id: str) -> Voice:
		return self._voices[voice_id]

	def __iter__(self) -> Iterator[Voice]:
	    return iter(self._voices.values())

	def __len__(self) -> int:
		return len(self._voices)

	def __repr__(self) -> str:
		return f"<VoiceManager for {len(self)} Voice(s) on the {self._organ.name} pipe organ>"
