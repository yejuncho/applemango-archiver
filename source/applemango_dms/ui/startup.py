import tkinter as tk
from tkinter import messagebox

import applemango_dms.state as state

from applemango_dms.services.auth import (
    load_saved_credentials,
    authenticate_to_server,
    update_session_login,
    clear_saved_credentials,
    clear_session_login,
)


def show_startup_screen(app):
    app._stop_login_connectivity_polling()
    app._center_window(420, 560)
    app.root.title("애플망고 DMS")
    app.clear_screen()
    app.root.configure(bg="white")

    shell = tk.Frame(app.root, bg="white")
    shell.pack(fill="both", expand=True)

    logo_label = tk.Label(shell, bg="white")
    logo_label.place(relx=0.5, rely=0.45, anchor="center")

    logo_photo = app._load_startup_logo_photo(max_width=300, max_height=180)
    app.startup_logo_image = logo_photo
    if logo_photo is not None:
        logo_label.configure(image=logo_photo)
    else:
        logo_label.configure(text="HISCOM", font=app._font(30, "bold"), fg="#1d2138")

    app.root.after(1200, app.route_from_startup)


def route_from_startup(app):
    state.is_demo_mode = False
    saved = load_saved_credentials()
    if not saved:
        app.show_login_screen()
        return

    ok, err = authenticate_to_server(saved["username"], saved["password"])
    if ok:
        update_session_login(saved["username"], saved["password"])
        app.show_workspace_selection_screen()
        return

    clear_saved_credentials()
    clear_session_login()
    app.show_login_screen(prefill_username=saved.get("username"))

    startup_msg = "저장된 로그인으로 NAS 연결에 실패했습니다.\n아이디/패스워드를 다시 입력해 주세요."
    if "1219" in str(err):
        startup_msg = (
            "이전 NAS 연결 정보와 충돌해 자동 로그인이 실패했습니다.\n"
            "연결을 정리한 뒤 로그인 화면으로 이동했습니다.\n"
            "아이디/패스워드를 다시 입력해 주세요."
        )
    messagebox.showinfo("자동 로그인 실패", startup_msg, parent=app.root)
