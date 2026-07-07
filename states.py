from aiogram.fsm.state import State, StatesGroup


class SongStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_vocal = State()
    waiting_for_name = State()
    waiting_for_relationship = State()
    waiting_for_facts = State()
    waiting_for_laugh_phrase = State()
    waiting_for_occasion = State()
    waiting_for_style = State()
    waiting_for_edited_lyrics = State()
