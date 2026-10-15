"""Usa o cliente Flet incluído no executável, sem baixar na primeira abertura."""
import os
import sys

os.environ['FLET_VIEW_PATH'] = os.path.join(sys._MEIPASS, 'flet_runtime')
