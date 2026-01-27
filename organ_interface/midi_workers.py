from loguru import logger
from queue import Queue, Empty
from mido import open_output, get_output_names, Message as MidiMessage
from mido.ports import BaseOutput
from threading import Thread
from time import monotonic_ns, sleep

from .organ import NoteEvent

class MidiOutput:
    STOP_EVENT: object = object()

    def __init__(self, config: dict[str, any]) -> None:
        self._config: dict[str, any] = config
        self._port_name: str
        self._magic_assign_midi_port()
        self._stop_event: type(MidiOutput.STOP_EVENT) = MidiOutput.STOP_EVENT
        self._queue: Queue[object] = Queue(maxsize=config.get("queue_size"))
        self._min_gap_ns = config.get('min_gap_ns')
        self._thread: Thread|None = None

    def _magic_assign_midi_port(self) -> None:
        for port_str in get_output_names():
            if any(name in port_str for name in self._config.get("midi_interface_names", [])):
                self._port_name = port_str
                return

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
                
                ns_per_s: int= 1_000_000_000
                min_gap_ns: int = self._min_gap_ns
                last_send_ts: int = 0
                now: int = monotonic_ns()
                delta: int = 0

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
                        msg.midi_complete()
                        continue
                    #logger.debug(f"SENDING <{msg.midi_message}> to {port}")
                    
                    now = monotonic_ns()
                    delta = now - last_send_ts
                    sleep(max(0, (min_gap_ns - delta) / ns_per_s))
                    
                    port.send(msg.midi_message)
                    
                    last_send_ts = monotonic_ns()

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
        
