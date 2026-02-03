from queue import Queue, Full
from loguru import logger

import time

from organ_interface.organ import Organ, Register, Note, Stop, NoteEvent, StopEvent
from organ_interface.note_attributes import NoteName, NoteAction, get_note_subset
from organ_interface.voices import RatioVoice, VoiceManager, Voice

from .scenes import Scene, get_all_notes, RepeatsAllowedScene, FavourLowScene, FavourHighScene

import random

class SongManager:
    def __init__(self, vm: VoiceManager, organ: Organ) -> None:
        self._vm: VoiceManager = vm
        self._vc = vm.get_voice_controller(RatioVoice)
        self._organ: Organ = organ
        self._queue: Queue = vm.queue
        self._registers: list[Register] = list(organ)
        self._stops: dict[NoteName, Stop] = {s.name: s for r in self._registers for s in r.stops if s.duplicates is False and s.effect is False}

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

    def _get_notes_by_int(self, nums: list[int]) -> list[NoteName]:
        return [NoteName(n) for n in nums]

    def _queue_event(self, event: NoteEvent|StopEvent):
        try:
            self._queue.put(event)
        except Full:
            logger.error(f"Queue is full. Dropped: {event}")

    def stop_intro(self) -> None:
        all_stops: list[Stop] = list(self._stops.values())
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
        r_pedal = self._organ["Pedal"]
        n = {r: notes for r in self._registers if r != r_pedal}
        n[r_pedal] = []
        for note in notes:
            if note >= r_pedal.lowest_note_name and note <= r_pedal.highest_note_name:
                n[self._organ["Pedal"]].append(note)
                continue
            n_temp = note
            while n_temp > r_pedal.highest_note_name:
                n_temp = NoteName(n_temp.value - 24)
            if n_temp < r_pedal.lowest_note_name:
                n_temp = NoteName(n_temp.value + 12)
            n[self._organ["Pedal"]].append(n_temp)
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

        TESTING: bool = False
        LINEAR_FINALE: bool = False
        LOAD_FINALE_STOPS: bool = True
        ONLY_PLAY_FINALE: bool = False

        EXTRA_VOICE_COUNT: int = 10

        vm = self._vm
        organ = self._organ
        vc = self._vc
        #pedal = organ['Pedal']

        # Ensure each register has a voice.
        for r in organ:
            vm.create_voice(f"{r.name}-init-1", r, RatioVoice) 
            vm.create_voice(f"{r.name}-init-2", r, RatioVoice) 

        stop_set_soft = [1, 14, 33, 53, 69]
        stop_set_2 = [2, 12, 35, 55, 79]
        stop_set_3 = [72, 61, 44, 24]

        finale_stops = [
            0, 3, 5,
            14, 17, 24, 19, 
            33, 38, 45,
            52, 54, 57,
            67, 73, 79
        ]

        # Create Random Stops for after the soft stops
        random_stops_1 = []
        exclude_1 = stop_set_soft
        for k in range(3):
            stops = []
            for r in organ:
                stop_ints = [s.name.value for s in r.stops if (s.size is not None or s.mixture is not None) and s.name.value not in exclude_1]
                stops.append(random.choice(stop_ints))
            random_stops_1.append(stops)
            exclude_1 = stops

        random_stops_2 = []
        exclude_2 = [*stop_set_soft, *stop_set_2]
        for k in range(4):
            stops = []
            for r in organ:
                stop_ints = [s.name.value for s in r.stops if (s.size is not None or s.mixture is not None) and s.name.value not in exclude_2]
                stops.extend(random.sample(stop_ints, 2))
            random_stops_2.append(stops)
            exclude_2 = stops

        for v in vm:
            logger.info(v)

        # Play intro
        if not TESTING:
            self.stop_intro()

        scene_0 = RepeatsAllowedScene(self.get_adjusted_notes([NoteName.N60]))
        scene_1 = Scene(self.get_adjusted_notes([NoteName.N55, NoteName.N64]))

        starting_scenes_notes = [
            [48], # C
            [60, 72], # C & C
            [55, 43], # G & G
            [64, 76], # E & E
            [48, 55, 60, 72],
            [48, 55, 60, 64, 72, 76]
            ]

        starting_scenes = []
        for notes in starting_scenes_notes:
            starting_scenes.append(Scene(self.get_adjusted_notes(self._get_notes_by_int(notes))))

        logger.info("Loading scene_0")
        vm.load_front_scene(scene_0)  
        logger.info("Loading scene_1")      
        vm.load_scene(scene_1)

        vm.all_on()
        vm.set_all_voice_ratios(0.0)
        vm.queue_all_midi()

        logger.info("Setting initial stops")
        
        # Set soft stops
        if not TESTING:
            self._send_stop_events_by_int(5, stop_set_soft, NoteAction.PRESS)

        if not TESTING:
            time.sleep(1)

        if not ONLY_PLAY_FINALE:
            logger.info("Starting cycle")
            for k, scene in enumerate(starting_scenes):
                vc.cycle_notes(loop_time=0.02/(2*k+1))
                #for v in vm:
                #    print(v.notes)

                # Add an extra voice on step 5
                if k == 2:
                    for r in organ:
                        v = vm.create_voice(f"{r.name}-add-1", r, RatioVoice)
                        logger.info(f"New voice {v}")
                        n_0 = v.notes[0]
                        for rv in vm:
                            if rv.name == f"{r.name}-init-1":
                                logger.info(rv.active_note)
                                n_0 = rv.active_note
                                #logger.info(n_0)
                                break
                        v.active_note = n_0
                        v.assign_random_range(keep_current=True, reset=True)
                        v.on()
                        logger.info(f"Creating: {v}")
                    logger.info("Creating voice")
                #for r in organ:
                #    logger.info(f"Loading {r.name}: {[nn.pretty for nn in scene._register_notes[r]]}")
                self.reset_ranges()
                vm.load_scene(scene)
                logger.info(f"end of loop {k}")
                time.sleep(1)

            logger.info("Slow loop with possible full range")
            vc.cycle_notes(loop_time=0.02)

            time.sleep(4)
            self.reset_ranges()

            # Random stops:
            logger.info("Random Stops here")
            self._send_stop_events_by_int(0, stop_set_soft, NoteAction.RELEASE)
            for stops in random_stops_1:
                self._send_stop_events_by_int(0, stops, NoteAction.PRESS)
                vc.cycle_notes(loop_time=0.01)
                time.sleep(1)
                self.reset_ranges()
                self._send_stop_events_by_int(0, stops, NoteAction.RELEASE)

            time.sleep(1)

            logger.info("Second set of stops")    
            if not TESTING:        
                self._send_stop_events_by_int(2, stop_set_soft, NoteAction.PRESS)
                self._send_stop_events_by_int(4, stop_set_2, NoteAction.PRESS)
            else:
                time.sleep(2)

            self.reset_ranges()

            vc.cycle_notes(loop_time=0.01, steps=1000)
            self.reset_ranges()

            logger.info("Cycle through C with stop changes")
            last_stops = [*stop_set_soft, *stop_set_2]
            for stops in random_stops_2:
                vm.load_scene(scene_0, allow_same=True)
                vc.cycle_notes(loop_time=0.005, steps=1000)
                self.reset_ranges()
                self._send_stop_events_by_int(0, last_stops, NoteAction.RELEASE)
                self._send_stop_events_by_int(0, stops, NoteAction.PRESS)
                last_stops = stops
                vc.cycle_notes(loop_time=0.005, steps=1000)
                time.sleep(2)
                self.reset_ranges()

            logger.info("Quick through C load presets")
            vc.cycle_notes(loop_time=0.0005, steps=1000)
            self._send_stop_events_by_int(1, last_stops, NoteAction.RELEASE)
            self._send_stop_events_by_int(1, stop_set_3, NoteAction.PRESS)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.0005, steps=1000)
            self._send_stop_events_by_int(2, stop_set_2, NoteAction.PRESS)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.0005, steps=1000)
            self._send_stop_events_by_int(2, stop_set_soft, NoteAction.PRESS)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.0005, steps=1000)
            time.sleep(1)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.00005, steps=1000)
            time.sleep(0.5)
            self.reset_ranges()
            
            for k in range(15):
                vc.cycle_notes(loop_time=0.00005, steps=1000)
                self.reset_ranges()  
            #time.sleep(2)

            vc.cycle_notes(loop_time=0.0001, steps=1000)
            #time.sleep(0.5)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.0005, steps=1000)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.001, steps=1000)
            self.reset_ranges()
            vc.cycle_notes(loop_time=0.005, steps=1000)
            time.sleep(1)
            self.reset_ranges()

            logger.info(f"Loading {EXTRA_VOICE_COUNT} more voices")
            for k in range(EXTRA_VOICE_COUNT):
                v = self.add_voice()
                logger.info(f"New voice: {v.active_note.pretty} on {v.register.name}")
                time.sleep(1)

            time.sleep(2)

            self.reset_ranges()
            
            logger.info("Slow Cycles")
            for k in range(2):
                vc.cycle_notes(loop_time=0.01, steps=1000)
                v = self.add_voice()
                logger.info(f"New voice: {v.active_note.pretty} on {v.register.name}")
                time.sleep(2)
                self.reset_ranges()

        if LOAD_FINALE_STOPS:
            logger.info("Loading finale stops")
            self._send_stop_events(0, [s for s in list(self._stops.values()) if s not in finale_stops], NoteAction.RELEASE)
            self._send_stop_events_by_int(0, finale_stops, NoteAction.PRESS)

        logger.info("Fast Cycles")
        for k in range(2):
            vc.cycle_notes(loop_time=0.001, steps=1000)
            v = self.add_voice()
            logger.info(f"New voice: {v.active_note.pretty} on {v.register.name}")
            time.sleep(2)
            self.reset_ranges()
        
        time.sleep(3)
        
        logger.info(f"final rise with {len(vm)} voices")

        if not TESTING:
            vc.cycle_notes(loop_time=0.06, steps=1000)
        else:
            vc.cycle_notes(loop_time=0.005, steps=1000)

        logger.info("Creating all the voices.")
        queue = vm.queue
        new_voices = []
        for r in organ:
            all_notes = get_note_subset(r.note_names, ["C", "E", "G"])
            for n in r:
                if n.state.active:
                    logger.info(f"{n.name.pretty} already playing on {r.name}")
                    all_notes.remove(n.name)
            for num, note in enumerate(reversed(all_notes)):
                v = vm.create_voice(f"{r.name}-finale-{num}", r, RatioVoice) 
                v.active_note = note
                v.assign_random_range(keep_current=True, reset=True)
                new_voices.append(v)
                logger.info(f"Creating new voice: {v}")

        if LINEAR_FINALE:
            logger.info("Setting all stops")
            #if not TESTING:
            all_stops = list(self._stops.values())
            random.shuffle(all_stops)
            logger.info(all_stops)
            self._send_stop_events(10, all_stops, NoteAction.PRESS)

            random.shuffle(new_voices)
            for v in new_voices:
                v.on()
                v.queue_midi(queue)
                logger.info(f"Starting new voice: {v}")
                time.sleep(0.25)
        else:
            logger.info("Doing mixed finale")
            all_stops = [s for s in list(self._stops.values()) if not s.state.active]
            #random.shuffle(all_stops)

            combined = all_stops + new_voices
            random.shuffle(combined)
            for obj in combined:
                match obj: 
                    case Stop():
                        se = obj.get_stop_event(NoteAction.PRESS)
                        self._queue_event(se)
                        logger.info(f"Turning on stop {obj}")
                    case Voice():
                        obj.on()
                        obj.queue_midi(queue)
                        logger.info(f"Starting new voice: {obj}")
                    case _:
                        logger.warning(f"Unexpected object in finale: {obj!r}")
                time.sleep(0.25)

        logger.info("FIN.")
        time.sleep(6)

        vm.all_off()
        vm.queue_all_midi()

        time.sleep(1)

        self._send_stop_events(0, self._stops.values(), NoteAction.RELEASE)

        ### ###
        # Ensure the correct note on the final scene
        # Pick a solid stop combo for the final climb.
        # Make it possible to test each section.


        #final_scene = FavourLowScene(get_all_notes(organ, key_notes=["C", "E", "G"]))


        #final_stops = [73, 68]

        #final_scene = FavourLowScene(get_all_notes(organ, key_notes=["C", "E", "G"]))
