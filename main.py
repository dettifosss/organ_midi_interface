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
import mido



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
        logger.info("RASS 1")
        rvc.cycle_notes(loop_time=0.005, steps=100, timing=True)
        logger.info("RASS 2")
        #wvc.cycle_notes()
        logger.info("RASS 3")
        time.sleep(2)
        while not queue.empty():
            time.sleep(0.5)
        logger.info("RASS 4")
        try:
            logger.info("RASS 5")
            vm.assign_random_ranges(["C", "E", "G"], keep_current = True)
            logger.info("RASS 6")
        except ValueError as e:
            logger.info("RASS 7")
            logger.error(e)
            for v in vm: 
                logger.info("RASS 8")
                print(v)
        logger.info("RASS 9")
        

    logger.debug("Gonna turn off")
    vm.all_off()
    vm.queue_all_midi()
    logger.debug("Should be quiet!")


def main() -> None:

    logger.info("Tentative Name:")
    logger.info("Organ Iced Chaos")

    if True:
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

    #midi_port = get_midi_port()
    #logger.info(f"Using MIDI port: {midi_port}")

    midi_output: MidiOutput = MidiOutput(midi_config)
    midi_output.start_midi_output_thread()

    vm = VoiceManager(organ, midi_output.queue)
    #vm.create_random_voices(1, voice_cls = WebVoice)
    vm.create_random_voices(54, voice_cls = RatioVoice)
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
