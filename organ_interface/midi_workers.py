from loguru import logger
from queue import Queue, Empty
from mido import open_output, get_output_names,Message as MidiMessage
from mido.ports import BaseOutput
from threading import Thread

from .organ import NoteEvent

class MidiOutput:
    STOP_EVENT: object = object()

    def __init__(self, port_name: str, queue_size: int=256) -> None:
        self._port_name: str = port_name
        self._stop_event: type(MidiOutput.STOP_EVENT) = MidiOutput.STOP_EVENT
        self._queue: Queue[object] = Queue(maxsize=queue_size)
        #self._active_note_events: list[NoteEvent] = []
        self._thread: Thread|None = None
        
    @property
    def queue(self) -> Queue[object]:
        return self._queue

    def panic(self, port: BaseOutput|None=None) -> None:
        if port is not None:
            try: 
                port.panic()
                #port.reset() # This might be needed instead.
                return
            #except (IOError, OSError, RuntimeError):
            except Exception as e:
                logger.warning(f"panic() failed: {e}")
                pass
        with open_output(self._port_name) as tmp_port:
            tmp_port.panic()

    def send_stop_event(self) -> None:
        logger.info("Sending STOP event to MidiOutput")

        try:
            while True:
                self._queue.get_nowait()
        except Empty:
            pass

        try:
            self._queue.put(self._stop_event, block=False)
        except Full:
            logger.warning("Queue full when sending STOP. Panic() instead.")
            self.panic()

    def midi_listener(self) -> None:
        with open_output(self._port_name) as port:
            try:
                while True:
                    try:
                        msg: NoteEvent|type(MidiOutput.STOP_EVENT) = self._queue.get(timeout=0.5)
                    except Empty:
                        continue
                    #logger.debug(f"Message received: {msg}")
                    if msg is self._stop_event:
                        logger.info("STOP event received.")
                        break
                    if msg.midi_message is None:
                        logger.debug(f"DROPPED {msg}")
                        continue
                    #logger.debug(f"SENDING <{msg.midi_message}> to {port}")
                    port.send(msg.midi_message)

                    msg.midi_complete()

            except (KeyboardInterrupt, SystemExit, OSError, IOError):
                logger.info("MIDI sender interrupted")
                port.panic()
            finally:
                logger.info("MIDI sender exiting")
                port.panic()

    def start_midi_output_thread(self) -> None:
        self.panic()
        self._thread: Thread = Thread(target=self.midi_listener, daemon=True)
        self._thread.start()
        
    def stop_midi_output_thread(self) -> None:
        self.send_stop_event()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._thread = None
        self.panic()
        
