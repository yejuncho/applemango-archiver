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

def _blend_hex(c1, c2, ratio):
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(r1 + (r2 - r1) * ratio)
    g = int(g1 + (g2 - g1) * ratio)
    b = int(b1 + (b2 - b1) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"

def _draw_rounded_rect(canvas, x1, y1, x2, y2, radius, fill, outline, width=1, tags=""):
    r = max(1, int(min(radius, (x2 - x1) / 2, (y2 - y1) / 2)))

    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="", tags=tags)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="", tags=tags)

    canvas.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=fill, outline="", tags=tags)
    canvas.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=fill, outline="", tags=tags)
    canvas.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=fill, outline="", tags=tags)
    canvas.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=fill, outline="", tags=tags)

    if width > 0:
        canvas.create_arc(x1, y1, x1 + 2 * r, y1 + 2 * r, start=90, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2 - 2 * r, y1, x2, y1 + 2 * r, start=0, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x1, y2 - 2 * r, x1 + 2 * r, y2, start=180, extent=90, style="arc", outline=outline, width=width, tags=tags)
        canvas.create_arc(x2 - 2 * r, y2 - 2 * r, x2, y2, start=270, extent=90, style="arc", outline=outline, width=width, tags=tags)

        canvas.create_line(x1 + r, y1, x2 - r, y1, fill=outline, width=width, tags=tags)
        canvas.create_line(x1 + r, y2, x2 - r, y2, fill=outline, width=width, tags=tags)
        canvas.create_line(x1, y1 + r, x1, y2 - r, fill=outline, width=width, tags=tags)
        canvas.create_line(x2, y1 + r, x2, y2 - r, fill=outline, width=width, tags=tags)

def _draw_horizontal_gradient_rounded(canvas, x1, y1, x2, y2, radius, start_color, end_color, tags=""):
    r = max(1, int(min(radius, (x2 - x1) / 2, (y2 - y1) / 2)))
    width_px = max(1, int(x2 - x1))
    for i in range(width_px):
        ratio = i / max(1, width_px - 1)
        color = _blend_hex(start_color, end_color, ratio)
        x = x1 + i
        if i < r:
            dx = r - i
            dy = int(r - max(0.0, (r * r - dx * dx)) ** 0.5)
        elif i > width_px - r:
            dx = i - (width_px - r)
            dy = int(r - max(0.0, (r * r - dx * dx)) ** 0.5)
        else:
            dy = 0
        canvas.create_line(x, y1 + dy, x, y2 - dy, fill=color, tags=tags)

def prepare_login_layout(app):
    target_w = 420
    target_h = 560
    login_bg_color = "#ffffff"
    app._center_window(target_w, target_h)
    app._apply_fullscreen_mode()
    app.root.title("애플망고 DMS - 로그인")
    app.clear_screen()
    app.root.configure(bg=login_bg_color)

    bg = tk.Canvas(app.root, bg=login_bg_color, highlightthickness=0, bd=0)
    bg.pack(fill="both", expand=True)
    app.login_bg_canvas = bg

    card_info = app.create_card(bg, height=494)
    content = card_info["content"]
    card_redraw = card_info["redraw"]

    def on_bg_resize(event):
        card_redraw(event.width // 2, event.height // 2)

    bg.bind("<Configure>", on_bg_resize)

    app.login_card = None
    app.login_content = content

def toggle_password_visibility(app, entry_widget, field_state, eye_widget=None):
    field_state["password_visible"] = not field_state["password_visible"]
    if field_state["password_visible"]:
        entry_widget.configure(show="")
        if eye_widget is not None:
            hide_icon = app.login_icon_photos.get("password_invisible")
            if hide_icon is not None:
                eye_widget.configure(image=hide_icon, text="")
                eye_widget.image = hide_icon
            else:
                eye_widget.configure(text="\U0001f648")
    else:
        entry_widget.configure(show="*")
        if eye_widget is not None:
            show_icon = app.login_icon_photos.get("password_visible")
            if show_icon is not None:
                eye_widget.configure(image=show_icon, text="")
                eye_widget.image = show_icon
            else:
                eye_widget.configure(text="\U0001f441")

def create_rounded_entry(app, parent, placeholder, icon_key, is_password=False):
    wrapper = tk.Frame(parent, bg="#f9f8ff")
    canvas = tk.Canvas(wrapper, height=52, bg="#f9f8ff", highlightthickness=0, bd=0)
    canvas.pack(fill="x")

    inner = tk.Frame(canvas, bg="#ffffff")
    inner_id = canvas.create_window(10, 5, window=inner, anchor="nw", height=42)

    leading_icon = app.login_icon_photos.get(icon_key)
    icon_label = tk.Label(inner, bg="#ffffff", fg="#868cab")
    if leading_icon is not None:
        icon_label.configure(image=leading_icon)
        icon_label.image = leading_icon
    else:
        fallback_text = "👤" if icon_key == "username" else "🔒"
        icon_label.configure(text=fallback_text, font=("Segoe UI Emoji", 11))
    icon_label.pack(side="left", padx=(12, 9))

    value_var = tk.StringVar(value="")
    entry = tk.Entry(
        inner,
        textvariable=value_var,
        show="*" if is_password else "",
        font=app._font(12),
        bd=0,
        relief="flat",
        highlightthickness=0,
        bg="#ffffff",
        fg="#1d2138",
        insertbackground="#06012a",
        insertontime=600,
        insertofftime=400,
        insertwidth=2,
    )
    entry.pack(side="left", fill="both", expand=True, pady=8)

    canvas.bind("<Button-1>", lambda _e: entry.focus_set())
    inner.bind("<Button-1>", lambda _e: entry.focus_set())
    icon_label.bind("<Button-1>", lambda _e: entry.focus_set())

    placeholder_label = tk.Label(inner, text=placeholder, font=app._font(11), bg="#ffffff", fg="#a0a3b8")
    placeholder_label.place(x=42, y=9)
    placeholder_label.bind("<Button-1>", lambda _e: entry.focus_set())

    field_state = {
        "focused": False,
        "password_visible": False,
    }

    eye_label = None
    if is_password:
        eye_icon = app.login_icon_photos.get("password_visible")
        eye_label = tk.Label(inner, bg="#ffffff", fg="#8086a3", cursor="hand2")
        if eye_icon is not None:
            eye_label.configure(image=eye_icon)
            eye_label.image = eye_icon
        else:
            eye_label.configure(text="\U0001f441", font=("Segoe UI Emoji", 13))
        eye_label.pack(side="right", padx=(6, 12))
        eye_label.bind("<Button-1>", lambda _e: toggle_password_visibility(app, entry, field_state, eye_label))

    def redraw_field(border_color):
        canvas.delete("field")
        w = max(40, canvas.winfo_width())
        h = max(40, canvas.winfo_height())
        app._smooth_rounded_rect(canvas, 1, 1, w - 1, h - 1, 16, fill="#ffffff", outline="", width=0, tags="field")
        app._smooth_rounded_rect(canvas, 1, 1, w - 1, h - 1, 16, fill="", outline=border_color, width=1, tags="field")
        canvas.tag_lower("field")
        canvas.itemconfigure(inner_id, width=max(10, w - 20))

    def update_placeholder(*_args):
        if value_var.get() or field_state["focused"]:
            placeholder_label.place_forget()
        else:
            placeholder_label.place(x=42, y=9)

    def on_focus_in(_event):
        field_state["focused"] = True
        redraw_field("#06012a")
        placeholder_label.place_forget()

    def on_focus_out(_event):
        field_state["focused"] = False
        redraw_field("#e4e6f0")
        update_placeholder()

    canvas.bind("<Configure>", lambda _e: redraw_field("#06012a" if field_state["focused"] else "#e4e6f0"))
    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)
    value_var.trace_add("write", update_placeholder)

    redraw_field("#e4e6f0")
    update_placeholder()

    return {
        "wrapper": wrapper,
        "entry": entry,
        "var": value_var,
        "get_value": lambda: value_var.get().strip(),
        "set_value": lambda value: value_var.set(value),
        "focus": lambda: entry.focus_set(),
        "eye": eye_label,
    }

def create_primary_login_button(app, parent, text, command):
    canvas = tk.Canvas(parent, height=52, bg="#f9f8ff", highlightthickness=0, bd=0, cursor="arrow")

    state = {
        "enabled": False,
        "hover": False,
    }

    def render():
        canvas.delete("btn")
        w = max(120, canvas.winfo_width())
        h = max(52, canvas.winfo_height())

        if state["enabled"]:
            start = "#06012a"
            end = "#2a2559" if not state["hover"] else "#37306c"
            border = "#19144a"
            text_color = "white"
            cursor = "hand2"
        else:
            start = "#b8bdd1"
            end = "#c5c9d9"
            border = "#b8bdd1"
            text_color = "#f6f7fb"
            cursor = "arrow"

        canvas.configure(cursor=cursor)
        _draw_horizontal_gradient_rounded(canvas, 1, 1, w - 1, h - 1, 16, start, end, tags="btn")
        _draw_rounded_rect(canvas, 1, 1, w - 1, h - 1, 16, fill="", outline=border, width=1, tags="btn")
        canvas.create_text(w // 2, h // 2, text=text, fill=text_color, font=app._font(13, "bold"), tags="btn")

    def on_enter(_event):
        state["hover"] = True
        render()

    def on_leave(_event):
        state["hover"] = False
        render()

    def on_click(_event):
        if state["enabled"]:
            command()

    canvas.bind("<Configure>", lambda _e: render())
    canvas.bind("<Enter>", on_enter)
    canvas.bind("<Leave>", on_leave)
    canvas.bind("<Button-1>", on_click)

    def set_enabled(enabled):
        state["enabled"] = bool(enabled)
        if not state["enabled"]:
            state["hover"] = False
        render()

    canvas.set_enabled = set_enabled
    render()
    return canvas

def show_login_screen(app, prefill_username=None):
    app._stop_login_connectivity_polling()
    state.is_demo_mode = False
    prepare_login_layout(app)

    frame = tk.Frame(app.login_content, bg="#ffffff")
    frame.pack(fill="both", expand=True)

    logo_photo = app._load_random_login_logo_photo(max_width=280, max_height=100)
    app.logo_image = logo_photo
    if logo_photo is not None:
        tk.Label(frame, image=logo_photo, bg="#ffffff").pack(pady=(0, 8))
    else:
        tk.Label(frame, text="애플망고", font=app._font(25, "bold"), fg="#06012a", bg="#ffffff").pack(pady=(0, 0))

    tk.Label(frame, text="DMS - 데이터 관리 시스템", font=app._font(12, "bold"), fg="#06012a", bg="#ffffff").pack(pady=(0, 25))

    username_field = create_rounded_entry(app, frame, "사용자명", "username", is_password=False)
    username_field["wrapper"].pack(fill="x")
    tk.Frame(frame, bg="#ffffff", height=10).pack(fill="x")

    password_field = create_rounded_entry(app, frame, "비밀번호", "password", is_password=True)
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
                bg="#ffffff",
                activebackground="#ffffff",
                fg="#3f4563",
                selectcolor="#ffffff",
                font=app._font(font_size),
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
            ).pack(side="left")
            return

        wrapper = tk.Frame(parent, bg="#ffffff", cursor="hand2")
        wrapper.pack(side="left")

        icon_label = tk.Label(
            wrapper,
            image=checked_icon if variable.get() else unchecked_icon,
            bg="#ffffff",
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
            bg="#ffffff",
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
    remember_row = tk.Frame(frame, bg="#ffffff")
    remember_row.pack(fill="x", pady=(12, 2))
    create_login_checkbox(remember_row, "로그인 정보 저장", remember_var, font_size=10)

    demo_mode_row = tk.Frame(frame, bg="#ffffff")
    demo_mode_row.pack(fill="x", pady=(0, 16))
    create_login_checkbox(demo_mode_row, "로컬 데모 모드 (NAS 없이 실행)", demo_mode_var, font_size=9)

    def submit_login():
        username = username_field["get_value"]()
        password = password_field["get_value"]()
        state.is_demo_mode = bool(demo_mode_var.get())

        if state.is_demo_mode:
            normalized_username = username.strip() or "test"
            account_name = normalized_username
            if "\\" in account_name:
                account_name = account_name.split("\\")[-1]
            if "@" in account_name:
                account_name = account_name.split("@")[0]

            state.session_logged_in = True
            state.session_username = normalized_username
            state.session_password = ""
            state.session_account_name = account_name

            if remember_var.get() and username.strip() and password:
                save_credentials(username, password)
            else:
                clear_saved_credentials()

            app.show_workspace_selection_screen()
            return

        if not username or not password:
            messagebox.showerror("로그인", "사용자명과 비밀번호를 입력하세요.", parent=app.root)
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

    login_btn = create_primary_login_button(app, frame, "로그인", submit_login)
    login_btn.pack(fill="x")

    connectivity_row = tk.Frame(frame, bg="#ffffff")
    connectivity_row.pack(fill="x", pady=(14, 0), side="bottom")
    
    connectivity_center = tk.Frame(connectivity_row, bg="#ffffff")
    connectivity_center.pack(anchor="center")

    dot_canvas = tk.Canvas(connectivity_center, width=10, height=10, bg="#ffffff", highlightthickness=0, bd=0)
    dot_item = dot_canvas.create_oval(1, 1, 9, 9, fill="#d23b3b", outline="#d23b3b")
    dot_canvas.pack(side="left", pady=(0, 1))

    status_label = tk.Label(
        connectivity_center,
        text="NAS 연결 불가",
        font=app._font(9),
        fg="#8d90a6",
        bg="#ffffff",
        anchor="w",
    )
    status_label.pack(side="left", padx=(6, 0))

    app.login_connectivity["dot_canvas"] = dot_canvas
    app.login_connectivity["dot_item"] = dot_item
    app.login_connectivity["label"] = status_label
    app._start_login_connectivity_polling()

    def update_login_button(*_args):
        if demo_mode_var.get():
            login_btn.set_enabled(True)
            return
        has_username = bool(username_field["get_value"]())
        has_password = bool(password_field["get_value"]())
        login_btn.set_enabled(has_username and has_password)

    username_field["var"].trace_add("write", update_login_button)
    password_field["var"].trace_add("write", update_login_button)
    demo_mode_var.trace_add("write", update_login_button)
    username_field["entry"].bind("<Return>", lambda _e: password_field["focus"]())
    password_field["entry"].bind("<Return>", lambda _e: submit_login())
    update_login_button()

    app.root.after(30, username_field["focus"])

def show_username_login_screen(app):
    app.show_login_screen()

def show_password_login_screen(app, username):
    app.show_login_screen(prefill_username=username)