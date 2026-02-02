from loguru import logger

from organ_interface.note_attributes import NoteName, get_note_subset
from organ_interface.organ import Organ, Register

import random

def get_all_notes(
        organ: Organ,
        key_notes: list[str] = ["C", "E", "G"]
    ) -> dict[Register, list[NoteName]]:
    
    all_in_key: list[NoteName] = get_note_subset(list(NoteName), key_notes)
    all_register_notes = {}

    for r in organ: 
        all_register_notes[r] = [n for n in all_in_key if n <= r.highest_note.name]

    return all_register_notes

class Scene:
    def __init__(self, register_notes: dict[Register, list[NoteName]]) -> None:
        self._register_notes_copy = {
            r: notes.copy()
            for r, notes in register_notes.items()
        }
        self._register_notes = {
            r: notes.copy()
            for r, notes in register_notes.items()
        }        
        self._taken_notes = {r: [] for r in register_notes.keys()}

    def reset(self) -> None:
        self._register_notes = {
            r: notes.copy()
            for r, notes in self._register_notes_copy.items()
        }
        self._taken_notes = {r: [] for r in self._register_notes.keys()}

    def get_note(self, register: Register, exclude: NoteName|None=None) -> NoteName:
        try:
            included_notes: list[NoteName] = [n for n in self._register_notes[register] if exclude is None or n != exclude]
            selected = self._choose_note(included_notes)
            self._take_note(register, selected)
        except IndexError:
            logger.warning(f"Out of notes in {register.name} when trying to assign. Need to re-use.")
            selected = random.choice(self._register_notes_copy[register])
        return selected

    def _take_note(self, register: Register, note: NoteName) -> None:
        self._taken_notes[register].append(note)
        self._register_notes[register].remove(note)

    def _choose_note(self, notes: list[NoteName]) -> NoteName:
        return random.choice(notes)

class FavourLowScene(Scene):
    def _choose_note(self, notes: list[NoteName]) -> NoteName:
        return notes[0]

class FavourHighScene(Scene):
    def _choose_note(self, notes: list[NoteName]) -> NoteName:
        return notes[-1]

class RepeatsAllowedScene(Scene):
    def _take_note(self, register: Register, note: NoteName) -> None:
        self._taken_notes[register].append(note)

class SpreadOut(Scene):
    def _choose_note(self, notes: list[NoteName]) -> NoteName:
        return
        if len(self._taken_notes) == 0 or len(notes) == 1:
            return notes[0]
        if len(self._taken_notes) == 1:
            return notes[-1]

