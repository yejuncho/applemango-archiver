import ctypes
import tkinter as tk

import applemango_dms.config as config

def apply_window_icon(window):
    # Set process identity for taskbar grouping/icon handling on Windows.
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HISCOM.AppleMangoDMS")
    except Exception:
        pass

    def _set_icon():
        try:
            icon_path = config.PROJECT_ROOT / "assets" / "images" / "hiscom.png"
            if not icon_path.exists():
                return

            try:
                icon_image = tk.PhotoImage(master=window, file=str(icon_path))
            except Exception:
                icon_image = None

            if icon_image is None:
                return

            window.iconphoto(True, icon_image)
            window._app_window_icon = icon_image
        except Exception:
            pass

    try:
        window.after(0, _set_icon)
    except Exception:
        _set_icon()