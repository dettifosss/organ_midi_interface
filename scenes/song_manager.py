from queue import Queue, Full
from loguru import logger

import time

from organ_interface.organ import Organ, Register, Note, Stop, NoteEvent, StopEvent
from organ_interface.note_attributes import NoteName, NoteAction
from organ_interface.voices import RatioVoice, VoiceManager, Voice

from .scenes import Scene, get_all_notes, RepeatsAllowedScene, FavourLowScene, FavourHighScene, Scene

class SongManager:
	def __init__(self, vm: VoiceManager, organ: Organ) -> None:
		self._vm: VoiceManager = vm
		self._vc = vm.get_voice_controller(RatioVoice)
		self._organ: Organ = organ
		self._queue: Queue = vm.queue
		self._registers: list[Register] = list(organ)
		self._stops: dict[NotaName, Stop] = {s.name: s for r in self._registers for s in r.stops if s.duplicates is False and s.effect is False}

	def _send_stop_events(self, time_taken:int, stops: list[Stop], action: NoteAction=NoteAction.PRESS, sleep_first: bool=True) -> None:
		if len(stops) <= 0:
			return
		se: StopEvent
		delay: float = time_taken / len(stops)
		for s in stops:
			if sleep_first:
				time.sleep(delay)
			se = s.get_stop_event(action)
			if not sleep_first:
				time.sleep(delay)
			self._queue_event(se)

	def _send_stop_events_by_int(self, time_taken: int, nums: list[int], action: NoteAction=NoteAction.PRESS, sleep_first:bool=True) -> None:
		stops: list[Stop] = self._get_stops_by_int(nums)
		self._send_stop_events(time_taken, stops, action, sleep_first)

	def _get_stops(self, note_names: list[NoteName]) -> list[Stop]:
		return [s for n, s in self._stops.items() if n in note_names]

	def _get_stops_by_int(self, nums: list[int]) -> list[Stop]:
		return self._get_stops([NoteName[f"N{n}"] for n in nums])

	def _queue_event(self, event: NoteEvent|StopEvent):
		try:
			self._queue.put(event)
		except Full:
			logger.error(f"Queue is full. Dropped: {event}")

	def stop_intro(self) -> None:
		all_stops: list[Stop] = self._stops.values()
		n_stops: int = len(self._stops)
		self._send_stop_events(8, all_stops, NoteAction.PRESS)
		self._send_stop_events(6, all_stops, NoteAction.RELEASE)
		self._send_stop_events(4, all_stops, NoteAction.PRESS)
		self._send_stop_events(2, all_stops, NoteAction.RELEASE)
		self._send_stop_events(1, all_stops, NoteAction.PRESS)
		time.sleep(0.5)
		self._send_stop_events(0, all_stops, NoteAction.RELEASE)
		time.sleep(0.5)

	def get_adjusted_notes(self, notes: list[Note]) -> dict[Register, list[NoteName]]:
		n = {r: notes for r in self._registers if r.name != 'Pedal'}
		n[self._organ['Pedal']] = [NoteName(n.value - 12) for n in notes]
		return n

	def add_voice(self) -> Voice:
		v = self._vm.create_random_voice(voice_cls = RatioVoice)
		v.assign_random_range(["C", "E", "G"], reset=True, keep_current=False)
		v.on()
		v.queue_midi(self._queue)
		return v

	def reset_ranges(self) -> None:
		self._vm.assign_random_ranges(["C", "E", "G"], keep_current = True)
	
	def play_song(self) -> None:

		vm = self._vm
		organ = self._organ
		vc = self._vc
		#pedal = organ['Pedal']

		# Ensure each register has a voice.
		for r in organ:
			vm.create_voice(f"{r.name}-manual", r, RatioVoice) 

		for v in vm:
			logger.info(v)

		# Play intro
		self.stop_intro()
		
		scene_0 = RepeatsAllowedScene(self.get_adjusted_notes([NoteName.N60]))
		scene_1 = RepeatsAllowedScene(self.get_adjusted_notes([NoteName.N48, NoteName.N55, NoteName.N64, NoteName.N72]))
		scene_2 = RepeatsAllowedScene(self.get_adjusted_notes([NoteName.N48, NoteName.N55, NoteName.N60, NoteName.N64, NoteName.N72]))

		return

		vm.load_front_scene(scene_0)		
		vm.load_scene(scene_1)

		vm.all_on()
		vm.set_all_voice_ratios(0.0)
		vm.queue_all_midi()

		logger.info("Setting initial stops")
		# Set soft stops
		self._send_stop_events_by_int(5, [1, 14, 33, 53, 69], NoteAction.PRESS)

		time.sleep(1)

		logger.info("Starting cycle")
		for k in range(5):
			vc.cycle_notes(loop_time=0.02/(2*k+1), steps=1000)
			self.reset_ranges()
			vm.load_scene(scene_2)

			time.sleep(1)
			logger.info(f"Cycle {k} end")

		logger.info("Second set of stops")
		self._send_stop_events_by_int(4, [2, 12, 35, 55, 79], NoteAction.PRESS)

		#vm.assign_random_ranges(["C", "E", "G"], keep_current = True)
		self.reset_ranges()
		logger.info("all notes to C")
		vm.load_scene(scene_0, allow_same=True)
		vc.cycle_notes(loop_time=0.01, steps=1000)

		logger.info("More stops on C")
		self._send_stop_events_by_int(2, [72, 61, 44, 24])

		time.sleep(2)

		self.reset_ranges()
		vc.cycle_notes(loop_time=0.01, steps=1000)

		logger.info("Quick through C")
		self.reset_ranges()
		vm.load_scene(scene_0, allow_same=True)
		time.sleep(1)

		vc.cycle_notes(loop_time=0.001, steps=1000)

		self.reset_ranges()
		vc.cycle_notes(loop_time=0.001, steps=1000)
		
		time.sleep(2)
		
		logger.info("Loading 10 more voices")
		for k in range(10):
			v = self.add_voice()
			logger.info(f"New voice: {v.active_note.pretty} on {v.register.name}")
			time.sleep(0.5)

		time.sleep(3)

		self.reset_ranges()
		
		logger.info("Slow Cycles")
		for k in range(3):
			vc.cycle_notes(loop_time=0.01, steps=1000)
			self.add_voice()
			time.sleep(2)
			self.reset_ranges()


		logger.info("Fast Cycles")
		for k in range(3):
			vc.cycle_notes(loop_time=0.001, steps=1000)
			self.add_voice()
			time.sleep(2)
			self.reset_ranges()
		

		time.sleep(1)
		
		logger.info(f"final rise with {len(vm)} voices")

		vc.cycle_notes(loop_time=0.05, steps=1000)

		logger.info("Setting all stops")
		self._send_stop_events(10, self._stops.values(), NoteAction.PRESS)

		logger.info("finale")
		time.sleep(4)

	    vm.all_off()
	    vm.queue_all_midi()

		time.sleep(1)

		self._send_stop_events(0, self._stops.values(), NoteAction.RELEASE)


		#final_scene = FavourLowScene(get_all_notes(organ, key_notes=["C", "E", "G"]))


		#final_stops = [73, 68]

		#final_scene = FavourLowScene(get_all_notes(organ, key_notes=["C", "E", "G"]))
