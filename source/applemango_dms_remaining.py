import os
import re
import json
import importlib
import socket
import ctypes
import shutil
import sqlite3
import subprocess
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from datetime import date, datetime
from ctypes import wintypes
from pathlib import Path

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    _tkinterdnd2 = importlib.import_module("tkinterdnd2")
    DND_FILES = _tkinterdnd2.DND_FILES
    TkinterDnD = _tkinterdnd2.TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None

def main():
    app = SequenceArchiverApp()
    app.show_startup_screen()
    app.root.mainloop()


if __name__ == "__main__":
    main()
