import ctypes

def apply_window_icon(window):
    # Clear title-bar icons on Windows so no default Tk icon is shown.
    def _clear_icon_handle():
        try:
            hwnd = int(window.winfo_id())
            user32 = ctypes.windll.user32
            wm_seticon = 0x0080
            icon_small = 0
            icon_big = 1
            user32.SendMessageW(hwnd, wm_seticon, icon_small, 0)
            user32.SendMessageW(hwnd, wm_seticon, icon_big, 0)
        except Exception:
            pass

    try:
        window.after(0, _clear_icon_handle)
    except Exception:
        _clear_icon_handle()