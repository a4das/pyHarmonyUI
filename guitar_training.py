#!/usr/bin/env python3
"""Plot the live microphone signal(s) with matplotlib.

Matplotlib and NumPy have to be installed.
https://matplotlib.org/stable/api/animation_api.html

    '''
    Guitar tuner script based on the Harmonic Product Spectrum (HPS)
    MIT License
    Copyright (c) 2021 chciken
    See also https://www.chciken.com/digital/signal/processing/2020/05/13/guitar-tuner.html
    '''
"""
import tkinter
from datetime import datetime
from time import sleep
from tkinter import Button, Canvas, CENTER
from tkinter.ttk import Progressbar

from pyharmonytools.guitar.guitar_neck.neck import Neck
from pyharmonytools.harmony.note import Note

from mic_analyzer import MicAnalyzer, MicListener


class GuitarTraining(MicListener):
    # https://en.wikipedia.org/wiki/Chromesthesia
    # Scriabin's sound-to-color circle of fifths
    note_colors = {
        "C": "#FF0000", "G": "#FF8000", "D": "#FFFF00", "A": "#2FCD30",
        "E": "#C4F2FF", "B": "#8FCAFF", "F": "#AD0031",
        "Gb": "#808CFD", "Db": "#9100FF", "Ab": "#BC76FC", "Eb": "#B8448C", "Bb": "#AB677D",
        "F#": "#808CFD", "C#": "#9100FF", "G#": "#BC76FC", "D#": "#B8448C", "A#": "#AB677D"
    }

    def __init__(self):
        # guitar
        self.guitar_neck = Neck()
        self.MAX_FRET = self.guitar_neck.FRET_QUANTITY_CLASSIC
        self.MAX_STRING = len(self.guitar_neck.TUNING)
        # mic
        self.mic_analyzer = MicAnalyzer()
        self.mic_analyzer.add_listener(self)
        self.download_thread = None
        # UI widgets
        self.progress_bar = None
        self.start_button = None
        self.stop_button = None
        self.ui_root_tk = None
        self.fretboard = None
        # fret representation stuffs
        self.margin_N = 10
        self.margin_S = 10
        self.margin_E = 10
        self.margin_W = 20
        self.fingerings_tk_id = []
        self.fretboard_width = 500
        self.fretboard_height = 200
        self.string_interval_size = 0
        # song data
        self.sig_up = 4  # 4 fourths in a bar
        self.sig_down = 4  # dealing with fourths
        self.tempo = 60  # 4th per minute
        self.chrono = None
        self.start_time = None
        self.is_listening = False
        # captured notes
        self.song = []
        self.current_note = None
        self.previous_note = None

    def display(self, ui_root_tk: tkinter.Tk):
        self.ui_root_tk = ui_root_tk
        self.start_button = Button(ui_root_tk, text='Listen', command=self._do_start_hearing)
        self.start_button.grid(row=0, column=0)
        self.stop_button = Button(self.ui_root_tk, text='Stop', command=self._do_stop_hearing)
        self.stop_button.grid(row=0, column=0)
        self.stop_button.grid_remove()

        self.progress_bar = Progressbar(ui_root_tk, orient='horizontal', mode='indeterminate', length=280)
        self.progress_bar.grid(row=1, column=0)
        self.fretboard = Canvas(ui_root_tk, width=self.fretboard_width, height=self.fretboard_height,
                                borderwidth=1, background='gray')
        self.fretboard.grid(row=2, column=0)
        self.draw_fretboard()
        self.initialize_fingers()

    def __test_note_display(self):
        self.draw_finger_on_neck("D", the_string='E', the_fret=5)
        self.draw_finger_on_neck("D", the_string='A', the_fret=6)
        self.draw_finger_on_neck("D", the_string='D', the_fret=7)
        self.draw_finger_on_neck("D", the_string='G', the_fret=8)
        self.draw_finger_on_neck("D", the_string='B', the_fret=9)
        self.draw_finger_on_neck("D", the_string='e', the_fret=10)
        self.draw_note("A")
        self.draw_note("B")
        self.draw_note("C")
        self.draw_note("D")
        self.draw_note("E")
        self.draw_note("F")
        self.draw_note("G")
        self.draw_note("A#")
        self.draw_note("Ab")
        self.draw_note("Bb")
        self.draw_note("C#")
        self.draw_note("Db")
        self.draw_note("D#")
        self.draw_note("Eb")
        self.draw_note("F#")
        self.draw_note("Gb")
        self.draw_note("G#")

    def _do_nothing(self):
        pass

    def _do_start_hearing(self):
        self.stop_button.grid()
        self.start_button.grid_remove()
        self.start_time = datetime.now()
        self.progress_bar.start()
        self.mic_analyzer.do_start_hearing()

    def _do_stop_hearing(self):
        self.mic_analyzer.do_stop_hearing()
        self.progress_bar.stop()
        self.stop_button.grid_remove()
        self.start_button.grid()
        self.display_song()

    def set_current_note(self, new_note: str, heard_freq: float = 0.0, closest_pitch: float = 0.0):
        """

        :param new_note: eg "A#2" or "B3"
        :return:
        """
        # print("_set_current_note", new_note)
        if new_note == "-" or len(new_note) in [2, 3]:
            now = datetime.now()
            self.chrono = (now - self.start_time).microseconds
            self.add_note(new_note)
            self.previous_note = self.current_note
            self.unset_current_note()
            self.current_note = new_note
            if new_note != "-":
                self.draw_note(new_note)

    def change_note_visible_status(self, note_name, visible: bool):
        """

        :param note_name: with or without octave
        :return:
        """
        print("reveal" if visible else "hide", note_name)
        notes_id = self.fretboard.find_withtag(note_name)
        print(notes_id)
        for n_id in notes_id:
            self.fretboard.itemconfigure(n_id, state='normal' if visible else 'hidden')

    def unset_current_note(self, all_same_notes: bool = False):
        print("unset", self.current_note)
        if self.current_note and len(self.current_note) in [2, 3]:
            if all_same_notes:
                raw_note = self.current_note[0:len(self.current_note) - 1]
                self.change_note_visible_status(raw_note, False)
            else:
                self.change_note_visible_status(self.current_note, False)
            self.previous_note = self.current_note
            self.current_note = "-"

    def add_note(self, new_note):
        if self.previous_note != new_note:
            now = datetime.now()
            self.chrono = (now - self.start_time)
            self.song.append((new_note, self.chrono))
            print("add_note", self.current_note, (new_note, self.chrono))

    def display_song(self):
        for note in self.song:
            print(note[1], ":", note[0])

    def draw_note(self, note: str):
        print("draw note", note)
        raw_note = note[0:len(note) - 1]
        octave = int(note[-1:])
        pos = self.guitar_neck.find_positions_from_note(raw_note, octave)
        print("all notes", pos)
        for p in pos:
            self.draw_finger_on_neck(raw_note, p[0], p[1])

    def draw_finger_on_neck(self, note: str, the_string: str, the_fret: int):
        """

        :param note:
        :param the_string: E A D G B e
        :param the_fret:
        :return:
        """
        print(note, the_string, the_fret)
        self.change_note_visible_status(self.current_note, True)

    def draw_fretboard(self):
        self.fretboard.delete("all")
        height = self.fretboard_height
        width = self.fretboard_width
        print("canvas", height, width)
        self.string_interval_size = (height + self.margin_N) / self.MAX_STRING
        for string in range(0, self.MAX_STRING):
            self.fretboard.create_line(self.margin_W, self.margin_N + string * self.string_interval_size,
                                       width, self.margin_N + string * self.string_interval_size,
                                       fill="yellow", width=2)
            for fret in range(0, self.MAX_FRET):
                self.fretboard.create_line(self.margin_W + fret * width / self.MAX_FRET, self.margin_N,
                                           self.margin_W + fret * width / self.MAX_FRET,
                                           self.margin_N + (self.MAX_STRING - 1) * self.string_interval_size,
                                           fill="lightgray", width=1)
        # nut
        self.fretboard.create_line(self.margin_W, self.margin_N,
                                   self.margin_W, self.margin_N + (self.MAX_STRING - 1) * self.string_interval_size,
                                   fill="lightgray", width=5)
        string_id = 5
        font = ('Helvetica', 12)
        for s in self.guitar_neck.TUNING:
            self.fretboard.create_text(10, self.margin_N + self.string_interval_size * string_id, text=s,
                                       font=font, anchor=CENTER, fill="#000000")
            string_id -= 1

    def initialize_fingers(self):
        font = ('Helvetica', 10)
        width = 20
        for the_fret in range(0, self.MAX_FRET):
            for note in self.guitar_neck.TUNING:
                nw_x = self.margin_W + the_fret * self.fretboard_width / self.MAX_FRET + 3
                nw_y = self.string_interval_size * (self.MAX_STRING - self.guitar_neck.TUNING.index(note) - 1)
                se_x = nw_x + width
                se_y = nw_y + width
                raw_note_name = self.guitar_neck.find_note_from_position(note, the_fret)
                note_color = self.note_colors[raw_note_name]
                if 'b' in raw_note_name:
                    raw_note_name = Note.CHROMATIC_SCALE_SHARP_BASED[Note.CHROMATIC_SCALE_FLAT_BASED.index(raw_note_name)]
                tags = (raw_note_name, self.guitar_neck.octave[note][the_fret], raw_note_name + str(self.guitar_neck.octave[note][the_fret]))
                oval_id = self.fretboard.create_oval(nw_x, nw_y, se_x, se_y, fill=note_color,
                                                     outline=note_color, width=1, tags=tags)
                text_id = self.fretboard.create_text(nw_x + width / 2, nw_y + width / 2, text=raw_note_name, font=font,
                                                     anchor=CENTER, fill="#222222", tags=tags)
                self.fingerings_tk_id.append((oval_id, text_id))
                self.change_note_visible_status(raw_note_name, False)


if __name__ == "__main__":
    nt = GuitarTraining()
    root = tkinter.Tk()
    root.title('Harmony tools')
    root.geometry('800x600')
    nt.display(root)
    root.mainloop()
