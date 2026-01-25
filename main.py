from loguru import logger
from pathlib import Path
from organ_interface.organ import Organ, Register, Note, NoteState
from organ_interface.note_attributes import NoteName, NoteAction

from organ_interface.voices import VoiceManager, Voice, RatioVoice, ComputerVoice, WebVoice, VoiceController

import random
import time

from queue import Queue

from organ_interface.midi_workers import MidiOutput

ORGAN_CONFIG_FILE: str = "hallgrimskirkja.yml"
OUTPUT_PORT: str = "loopMIDI Port 2"

def test_voices(vm):
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
        rvc.cycle_notes(loop_time=0.0005, steps=1000, timing=True)
        wvc.cycle_notes()
        time.sleep(1)
        try:
            vm.assign_random_ranges(["C", "E", "G"], keep_current = True)
        except ValueError as e:
            logger.error(e)
            for v in vm: 
                print(v)
        continue

    logger.debug("Gonna turn off")
    vm.all_off()
    vm.queue_all_midi()
    logger.debug("Should be quiet!")

def main() -> None:

    if True:
        logger.remove()
        import sys
        logger.add(sys.stderr, level="INFO")

    organ_config_path = Path(__file__).resolve().parent / "config" / ORGAN_CONFIG_FILE
    organ: Organ = Organ(organ_config_path)

    logger.info(organ)
    for r in organ:
        logger.info(r)

    midi_output: MidiOutput = MidiOutput(OUTPUT_PORT)
    midi_output.start_midi_output_thread()

    vm = VoiceManager(organ, midi_output.queue)
    #vm.create_random_voices(1, voice_cls = WebVoice)
    #vm.create_random_voices(1, voice_cls = RatioVoice)
    #vm.assign_random_ranges(["C", "E", "G"], keep_current = False)

    #test_voices(vm)

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
