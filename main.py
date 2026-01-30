from loguru import logger
from pathlib import Path
from organ_interface.organ import Organ, Register, Note, NoteState
from organ_interface.note_attributes import NoteName, NoteAction
from organ_interface.helpers import load_config, get_full_path

from organ_interface.voices import VoiceManager, Voice, RatioVoice, ComputerVoice, WebVoice, VoiceController

import random
import time

from queue import Queue

from organ_interface.midi_workers import MidiOutput
from scenes.scenes import get_all_notes, Scene, FavourLowScene, FavourHighScene


def test_voices(vm, queue):
    logger.info(vm)
    for vc in vm.voice_controllers:
        logger.info(vc)
        for v in vc:
            logger.info(v)

    vm.all_on()
    rvc = vm.get_voice_controller(RatioVoice)
    wvc = vm.get_voice_controller(WebVoice)
    vm.set_all_voice_ratios(0.0)
    vm.queue_all_midi()
 
    time.sleep(1)

    for k in range(1):
        rvc.cycle_notes(loop_time=0.005, steps=1000, timing=True)
        #wvc.cycle_notes()
        time.sleep(2)
        while not queue.empty():
            time.sleep(0.5)
        try:
            vm.assign_random_ranges(["C", "E", "G"], keep_current = True)
        except ValueError as e:
            logger.error(e)
            for v in vm: 
                print(v)
        

    logger.debug("Gonna turn off")
    vm.all_off()
    vm.queue_all_midi()
    logger.debug("Should be quiet!")


def test_song(
        organ: Organ,
        vm: VoiceManager,
        q: Queue,
        start_scene: Scene,
        end_scene: Scene,
        loop_speed: float,
        loop_count: int,
        sleep_time: int
        ) -> None:

    vc = vm.get_voice_controller(RatioVoice)
    
    logger.info(vm)
    logger.info(vc)

    vm.assign_random_ranges(["C", "E", "G"], keep_current = True)
    vm.load_front_scene(start_scene)
    
    for v in vm:
        logger.info(v)

    vm.all_on()
    vm.set_all_voice_ratios(0.0)
    vm.queue_all_midi()

    time.sleep(sleep_time)

    for k in range(loop_count):
        vc.cycle_notes(loop_time=loop_speed, steps=1000, timing=True)


        for r in organ:
            stops = [s for s in r.stops if s.size is not None and not s.state.active]
            try:
                stop = random.choice(stops)
            except IndexError:
                logger.error(f"No more stops to pull on {r.name}.")
                continue
            stop_event = stop.get_stop_event(NoteAction.PRESS)
            q.put(stop_event)
            #logger.info(stop)
            #logger.info(stop_event)
            time.sleep(sleep_time/len(organ))

        vm.assign_random_ranges(["C", "E", "G"], keep_current = True)

    logger.info("Heading into final scene.")

    vm.load_scene(end_scene)
    vc.cycle_notes(loop_time=loop_speed*5, steps=1000, timing=True)

    for r in organ:
        for s in r.stops:
            se = s.get_stop_event(NoteAction.PRESS)
            logger.info(se)
            q.put(se)
            time.sleep(0.1)

    time.sleep(sleep_time*5)

    vm.all_off()

    for r in organ:
        for s in r.stops:
            se = s.get_stop_event(NoteAction.RELEASE)
            q.put(se)


def test_stops(organ: Organ, q: Queue):
    for r in organ:
        stops = [s for s in r.stops if s.size is not None]
        ss = random.sample(stops, 4)
        for s in ss:
            se = s.get_stop_event(NoteAction.PRESS)
            q.put(se)
            time.sleep(0.5)

    time.sleep(1)

    for r in organ:
        for s in r.stops:
            se = s.get_stop_event(NoteAction.RELEASE)
            q.put(se)

    time.sleep(1)

    for r in organ:
        for s in r.stops:
            se = s.get_stop_event(NoteAction.PRESS)
            q.put(se)

    time.sleep(1)

    for r in organ:
        for s in r.stops:
            se = s.get_stop_event(NoteAction.RELEASE)
            q.put(se)


def main() -> None:

    PANIC: bool = True
    PANIC: bool = False

    VOICE_COUNT: int = 10
    LOOP_SPEED: float = 0.01
    LOOP_COUNT: int = 4
    SLEEP_TIME: int = 2
    DEBUG_ON: bool = False
    TEST_STOPS: bool = False
    PLAY_SONG: bool = False
    USE_SONG_MANAGER: bool = True

    logger.info("#############################")
    logger.info("Glundroði fyrir orgel í C-dúr")
    logger.info("#############################")

    if not DEBUG_ON:
        logger.remove()
        import sys
        logger.add(sys.stderr, level="INFO")

    common_config = load_config(get_full_path("config/common.yml"))
    midi_config = common_config.get("midi_config")
    organ_config = load_config(get_full_path(f"config/{common_config.get('organ_config_file')}"))

    organ: Organ = Organ(organ_config)

    logger.info(organ)
    for r in organ:
        logger.info(r)

    midi_output: MidiOutput = MidiOutput(midi_config)
    midi_output.start_midi_output_thread()
    if PANIC:
        midi_output.send_stop_event()
        return

    queue: Queue = midi_output.queue
    
    vm = VoiceManager(organ, midi_output.queue)
    vm.create_random_voices(VOICE_COUNT, voice_cls = RatioVoice)  

    if USE_SONG_MANAGER:
        try:
            from scenes.song_manager import SongManager
            sm: SongManager = SongManager(vm, organ)
            sm.play_song()
        except Exception as e:
            midi_output.send_stop_event()
            raise e

    if TEST_STOPS:
        test_stops(organ, queue)
        time.sleep(1)

    # Turn on random stops for the start
    for r in organ:
        stops = [s for s in r.stops if s.size is not None]
        ss = random.sample(stops, 1)
        for s in ss:
            se = s.get_stop_event(NoteAction.PRESS)
            queue.put(se)

    # Create the start and end scenes
    final_scene_notes = get_all_notes(organ, key_notes=["C", "E", "G"])
    final_scene = FavourHighScene(final_scene_notes)

    start_scene_notes = {}
    for r in organ:
        start_scene_notes[r] = [NoteName.N60 for n in r]
    start_scene = Scene(start_scene_notes)

    if PLAY_SONG:
        #Test the song
        try:
            test_song(organ, vm, queue, start_scene, final_scene, LOOP_SPEED, LOOP_COUNT, SLEEP_TIME)
        except Exception as e:
            logger.error(f"Exception encountered during test song.")
            logger.error(e)

    midi_output.stop_midi_output_thread()
    midi_output.panic()


########
########
########

def main_OLD() -> None:

    logger.info("Tentative Name:")
    logger.info("Organ Iced Chaos")

    if False:
        logger.remove()
        import sys
        logger.add(sys.stderr, level="INFO")

    common_config = load_config(get_full_path("config/common.yml"))
    midi_config = common_config.get("midi_config")
    organ_config = load_config(get_full_path(f"config/{common_config.get('organ_config_file')}"))

    organ: Organ = Organ(organ_config)

    logger.info(organ)
    for r in organ:
        logger.info(r)

    midi_output: MidiOutput = MidiOutput(midi_config)
    midi_output.start_midi_output_thread()

    vm = VoiceManager(organ, midi_output.queue)
    #vm.create_random_voices(1, voice_cls = WebVoice)
    vm.create_random_voices(1, voice_cls = RatioVoice)

    q: Queue = midi_output.queue


    for r in organ:
        stops = [s for s in r.stops if s.size is not None]
        ss = random.sample(stops, 3)
        for s in ss:
            se = s.get_stop_event(NoteAction.PRESS)
            q.put(se)

    time.sleep(1)

    for r in organ:
        for s in r.stops:
            se = s.get_stop_event(NoteAction.RELEASE)
            q.put(se)
    
    time.sleep(1)

    for r in organ:
        stops = [s for s in r.stops if s.size is not None]
        ss = random.sample(stops, 3)
        for s in ss:
            se = s.get_stop_event(NoteAction.PRESS)
            q.put(se)
    

    if False:
        from scenes.scenes import get_all_notes, Scene, FavourLowScene, FavourHighScene
        final_scene_notes = get_all_notes(organ, key_notes=["C", "E", "G"])
        final_scene = FavourHighScene(final_scene_notes)

        start_scene_notes = {}
        for r in organ:
            start_scene_notes[r] = [NoteName.N60 for n in r]

        start_scene = Scene(start_scene_notes)

        vm.load_front_scene(start_scene)
        vm.load_scene(final_scene)
    else:
        vm.assign_random_ranges(["C", "E", "G"], keep_current = False)


    try:
        test_voices(vm, midi_output.queue)
    except KeyboardInterrupt:
        midi_output.stop_midi_output_thread()
        midi_output.panic()


    midi_output.stop_midi_output_thread()
    return

    from webserver import app
    app.state.voice_manager = vm

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    midi_output.stop_midi_output_thread()
    logger.info("AT THE END")


if __name__ == "__main__":

    if True:
        main()
    else:
        import cProfile
        import pstats

        profiler = cProfile.Profile()
        profiler.enable()       # start profiling
        main()
        profiler.disable()      # stop profiling

        stats = pstats.Stats(profiler)
        stats.strip_dirs()      # clean up file paths
        stats.sort_stats("cumulative")  # or "tottime"
        stats.print_stats(20)   # print top 20 functions
