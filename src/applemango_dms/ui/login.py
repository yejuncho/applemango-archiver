import tkinter as tk
from tkinter import messagebox

import applemango_dms.config as config
import applemango_dms.state as state

from applemango_dms.utils.images import load_svg_photo

from applemango_dms.services.auth import (
    load_saved_credentials,
    save_credentials,
    clear_saved_credentials,
    authenticate_to_server,
    update_session_login,
    clear_session_login,
)
from applemango_dms.services.nas import (
    check_local_network_connectivity,
)


def show_login_screen(app, prefill_username=None):
    app._stop_login_connectivity_polling()
    state.is_demo_mode = False
    app._prepare_login_layout()

    frame = tk.Frame(app.login_content, bg="#f9f8ff")
    frame.pack(fill="both", expand=True)

    logo_photo = app._load_random_login_logo_photo(max_width=280, max_height=100)
    app.logo_image = logo_photo
    if logo_photo is not None:
        tk.Label(frame, image=logo_photo, bg="#f9f8ff").pack(pady=(0, 8))
    else:
        tk.Label(frame, text="애플망고", font=app._font(25, "bold"), fg="#06012a", bg="#f9f8ff").pack(pady=(0, 0))

    tk.Label(frame, text="DMS - 데이터 관리 시스템", font=app._font(12, "bold"), fg="#06012a", bg="#f9f8ff").pack(pady=(0, 25))

    username_field = app.create_rounded_entry(frame, "사용자명", "username", is_password=False)
    username_field["wrapper"].pack(fill="x")
    tk.Frame(frame, bg="#f9f8ff", height=10).pack(fill="x")

    password_field = app.create_rounded_entry(frame, "비밀번호", "password", is_password=True)
    password_field["wrapper"].pack(fill="x")

    remembered = load_saved_credentials()
    if prefill_username:
        username_field["set_value"](str(prefill_username).strip())
    elif remembered and remembered.get("username") and not username_field["get_value"]():
        username_field["set_value"](remembered["username"])

    remember_var = tk.BooleanVar(value=remembered is not None)
    demo_mode_var = tk.BooleanVar(value=False)

    icon_dir = config.PROJECT_ROOT / "assets" / "icons" / "login"
    checked_icon = app.login_icon_photos.get("checked")
    unchecked_icon = app.login_icon_photos.get("unchecked")
    if checked_icon is None or unchecked_icon is None:
        checked_icon = checked_icon or load_svg_photo(icon_dir / "checked.svg", max_width=16, max_height=16)
        unchecked_icon = unchecked_icon or load_svg_photo(icon_dir / "unchecked.svg", max_width=16, max_height=16)

    def create_login_checkbox(parent, text, variable, *, font_size):
        if checked_icon is None or unchecked_icon is None:
            tk.Checkbutton(
                parent,
                text=text,
                variable=variable,
                bg="#f9f8ff",
                activebackground="#f9f8ff",
                fg="#3f4563",
                selectcolor="#f9f8ff",
                font=app._font(font_size),
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            ).pack(side="left")
            return

        wrapper = tk.Frame(parent, bg="#f9f8ff", cursor="hand2")
        wrapper.pack(side="left")

        icon_label = tk.Label(
            wrapper,
            image=checked_icon if variable.get() else unchecked_icon,
            bg="#f9f8ff",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        icon_label.pack(side="left", padx=(0, 6), pady=(0, 1))

        text_label = tk.Label(
            wrapper,
            text=text,
            font=app._font(font_size),
            fg="#3f4563",
            bg="#f9f8ff",
            cursor="hand2",
        )
        text_label.pack(side="left")

        def sync_icon(*_args):
            next_icon = checked_icon if variable.get() else unchecked_icon
            icon_label.configure(image=next_icon)
            icon_label.image = next_icon

        def toggle(_event=None):
            variable.set(not bool(variable.get()))

        variable.trace_add("write", sync_icon)
        for widget in (wrapper, icon_label, text_label):
            widget.bind("<Button-1>", toggle)

        sync_icon()
    remember_row = tk.Frame(frame, bg="#f9f8ff")
    remember_row.pack(fill="x", pady=(12, 2))
    create_login_checkbox(remember_row, "로그인 정보 저장", remember_var, font_size=10)

    demo_mode_row = tk.Frame(frame, bg="#f9f8ff")
    demo_mode_row.pack(fill="x", pady=(0, 16))
    create_login_checkbox(demo_mode_row, "로컬 데모 모드 (NAS 없이 실행)", demo_mode_var, font_size=9)

    def submit_login():
        username = username_field["get_value"]()
        password = password_field["get_value"]()
        if not username or not password:
            messagebox.showerror("로그인", "사용자명과 비밀번호를 입력하세요.", parent=app.root)
            return

        state.is_demo_mode = bool(demo_mode_var.get())

        if state.is_demo_mode:
            normalized_username = username.strip()
            account_name = normalized_username
            if "\\" in account_name:
                account_name = account_name.split("\\")[-1]
            if "@" in account_name:
                account_name = account_name.split("@")[0]

            state.session_logged_in = True
            state.session_username = normalized_username
            state.session_password = ""
            state.session_account_name = account_name

            if remember_var.get():
                save_credentials(username, password)
            else:
                clear_saved_credentials()

            app.show_workspace_selection_screen()
            return

        network_warning_msg = (
            "파일 서버(NAS)에 연결할 수 없습니다.\n\n"
            "사내 네트워크에 연결되어 있는지 확인한 후 다시 시도해 주세요."
        )

        is_network_connected, _ = check_local_network_connectivity(config.default_server_name)
        if not is_network_connected:
            messagebox.showerror("로그인 실패", network_warning_msg, parent=app.root)
            return

        ok, err = authenticate_to_server(username, password)
        if not ok:
            clear_session_login()
            is_network_issue = (
                "64" in err
                or "67" in err
                or "53" in err
                or "The specified network name is no longer available" in err
                or "지정된 네트워크 이름을 더 이상 사용할 수 없습니다" in err
                or "The network name cannot be found" in err
                or "네트워크 이름을 찾을 수 없습니다" in err
            )
            is_invalid_credentials = (
                "1326" in err
                or "Logon failure" in err
                or "unknown user name or bad password" in err
                or "사용자 이름 또는 암호가 올바르지 않습니다" in err
            )
            is_connection_conflict = "1219" in err

            if is_network_issue:
                messagebox.showerror("로그인 실패", network_warning_msg, parent=app.root)
            elif is_connection_conflict:
                messagebox.showerror(
                    "로그인 실패",
                    "기존 NAS 연결 정보와 충돌했습니다(1219).\n"
                    "연결 정보를 정리한 뒤 다시 시도해 주세요.",
                    parent=app.root,
                )
            elif is_invalid_credentials:
                messagebox.showerror("로그인 실패", "아이디/패스워드를 확인해주세요.", parent=app.root)
            else:
                messagebox.showerror("로그인 실패", err, parent=app.root)
            return

        update_session_login(username, password)
        if remember_var.get():
            save_credentials(username, password)
        else:
            clear_saved_credentials()

        app.show_workspace_selection_screen()

    login_btn = app._create_primary_login_button(frame, "로그인", submit_login)
    login_btn.pack(fill="x")

    connectivity_row = tk.Frame(frame, bg="#f9f8ff")
    connectivity_row.pack(fill="x", pady=(14, 0), side="bottom")

    connectivity_center = tk.Frame(connectivity_row, bg="#f9f8ff")
    connectivity_center.pack(anchor="center")

    dot_canvas = tk.Canvas(connectivity_center, width=10, height=10, bg="#f9f8ff", highlightthickness=0, bd=0)
    dot_item = dot_canvas.create_oval(1, 1, 9, 9, fill="#d23b3b", outline="#d23b3b")
    dot_canvas.pack(side="left", pady=(0, 1))

    status_label = tk.Label(
        connectivity_center,
        text="NAS 연결 불가",
        font=app._font(9),
        fg="#8d90a6",
        bg="#f9f8ff",
        anchor="w",
    )
    status_label.pack(side="left", padx=(6, 0))

    app.login_connectivity["dot_canvas"] = dot_canvas
    app.login_connectivity["dot_item"] = dot_item
    app.login_connectivity["label"] = status_label
    app._start_login_connectivity_polling()

    def update_login_button(*_args):
        has_username = bool(username_field["get_value"]())
        has_password = bool(password_field["get_value"]())
        login_btn.set_enabled(has_username and has_password)

    username_field["var"].trace_add("write", update_login_button)
    password_field["var"].trace_add("write", update_login_button)
    username_field["entry"].bind("<Return>", lambda _e: password_field["focus"]())
    password_field["entry"].bind("<Return>", lambda _e: submit_login())
    update_login_button()

    app.root.after(30, username_field["focus"])


def show_username_login_screen(app):
    app.show_login_screen()


def show_password_login_screen(app, username):
    app.show_login_screen(prefill_username=username)