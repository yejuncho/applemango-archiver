import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import applemango_dms.config as config
import applemango_dms.state as state

from applemango_dms.services.auth import clear_saved_credentials
from applemango_dms.services.nas import get_mapped_network_drives
from applemango_dms.ui import colors
from applemango_dms.utils.images import load_svg_photo
from applemango_dms.utils.windows import apply_window_icon

SETTINGS_BG = colors.BACKGROUND
SETTINGS_CARD_BG = colors.SURFACE_ALT
SETTINGS_CARD_BORDER = colors.BORDER
SETTINGS_ROW_BG = colors.SURFACE_ALT
SETTINGS_ROW_BORDER = colors.BORDER_LIGHT
SETTINGS_ROW_HOVER = colors.SURFACE_HOVER_SOFT
SETTINGS_ROW_DANGER_HOVER = colors.SURFACE_DANGER_HOVER

SETTINGS_TEXT_PRIMARY = colors.TEXT_PRIMARY
SETTINGS_TEXT_SECONDARY = colors.TEXT_SECONDARY
SETTINGS_TEXT_EMPHASIS = colors.TEXT_EMPHASIS
SETTINGS_TEXT_DANGER = colors.FAILED_STRONG

SETTINGS_ICON_DIR = config.PROJECT_ROOT / "assets" / "icons" / "settings"
SETTINGS_ICON_SIZE = 18
SETTINGS_WINDOW_WIDTH = 430
SETTINGS_WINDOW_HEIGHT = 520
SETTINGS_WINDOW_MIN_WIDTH = 380
SETTINGS_WINDOW_MIN_HEIGHT = 520
SETTINGS_ROW_SIDE_PAD = 28


def _center_toplevel_to_parent(parent_win, child_win):
    child_win.update_idletasks()
    parent_win.update_idletasks()

    parent_x = parent_win.winfo_rootx()
    parent_y = parent_win.winfo_rooty()
    parent_w = max(1, parent_win.winfo_width())
    parent_h = max(1, parent_win.winfo_height())

    child_w = max(1, child_win.winfo_width())
    child_h = max(1, child_win.winfo_height())

    x = parent_x + (parent_w - child_w) // 2
    y = parent_y + (parent_h - child_h) // 2
    child_win.geometry(f"{child_w}x{child_h}+{max(0, x)}+{max(0, y)}")


def show_placeholder(parent, title, message):
    messagebox.showinfo(title, message, parent=parent)


def _confirm_clear_saved_credentials(parent):
    confirmed = messagebox.askyesno(
        "저장된 로그인 정보 삭제",
        "로컬에 저장된 로그인 정보가 삭제됩니다.\n현재 로그인 세션은 유지됩니다.\n삭제하시겠습니까?",
        parent=parent,
    )
    if not confirmed:
        return

    clear_saved_credentials()
    messagebox.showinfo("설정", "저장된 로그인 정보를 삭제했습니다.", parent=parent)


def _load_settings_icon(owner, filename, *, size=SETTINGS_ICON_SIZE, tint=SETTINGS_TEXT_EMPHASIS):
    icon_size = size
    cache = getattr(owner, "_settings_icon_refs", None)
    if cache is None:
        cache = {}
        owner._settings_icon_refs = cache

    cache_key = f"{filename}:{icon_size}:{tint}"
    if cache_key in cache:
        return cache[cache_key]

    photo = load_svg_photo(
        SETTINGS_ICON_DIR / filename,
        max_width=icon_size,
        max_height=icon_size,
        tint=tint,
    )
    if photo is not None:
        cache[cache_key] = photo
    return photo


def _create_section_heading(app, parent, title, *, top_pad, icon_photo=None):
    heading_row = tk.Frame(parent, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    heading_row.pack(fill="x", pady=(top_pad, 6))

    if icon_photo is not None:
        icon_label = tk.Label(heading_row, image=icon_photo, bg=SETTINGS_CARD_BG, anchor="w")
        icon_label.image = icon_photo
        icon_label.pack(side="left", padx=(0, 6))

    tk.Label(
        heading_row,
        text=title,
        font=app._font(12, "bold"),
        fg=SETTINGS_TEXT_EMPHASIS,
        bg=SETTINGS_CARD_BG,
        anchor="w",
    ).pack(side="left")


def create_settings_row(
    app,
    parent,
    *,
    title,
    icon_photo,
    command,
    destructive=False,
):
    row_height = 56
    normal_bg = SETTINGS_ROW_BG
    hover_bg = SETTINGS_ROW_DANGER_HOVER if destructive else SETTINGS_ROW_HOVER
    title_color = SETTINGS_TEXT_DANGER if destructive else SETTINGS_TEXT_PRIMARY
    chevron_color = SETTINGS_TEXT_DANGER if destructive else SETTINGS_TEXT_SECONDARY
    fallback_color = SETTINGS_TEXT_DANGER if destructive else SETTINGS_TEXT_SECONDARY

    row = tk.Canvas(
        parent,
        bg=SETTINGS_CARD_BG,
        height=row_height,
        highlightthickness=0,
        bd=0,
        relief="flat",
        cursor="hand2",
    )

    row_state = {
        "hover": False,
        "shape": None,
    }

    icon_item = None
    if icon_photo is not None:
        icon_item = row.create_image(24, row_height // 2, image=icon_photo, tags=("row",))
        row._icon_ref = icon_photo
    else:
        icon_item = row.create_text(
            24,
            row_height // 2,
            text="*",
            font=app._font(12, "bold"),
            fill=fallback_color,
            tags=("row",),
        )

    title_item = row.create_text(
        52,
        row_height // 2,
        text=title,
        font=app._font(11, "bold"),
        fill=title_color,
        anchor="w",
        tags=("row",),
    )
    chevron_item = row.create_text(
        0,
        row_height // 2,
        text="\u203A",
        font=("Segoe UI Symbol", 16, "bold"),
        fill=chevron_color,
        anchor="e",
        tags=("row",),
    )

    def redraw(_event=None):
        width = max(80, row.winfo_width())
        height = max(row_height, row.winfo_height())
        fill = hover_bg if row_state["hover"] else normal_bg

        if row_state["shape"] is not None:
            row.delete(row_state["shape"])

        row_state["shape"] = app._smooth_rounded_rect(
            row,
            1,
            1,
            width - 1,
            height - 1,
            14,
            fill=fill,
            outline=SETTINGS_ROW_BORDER,
            width=1,
            tags=("row", "rowbg"),
        )
        row.tag_lower(row_state["shape"])

        row.coords(icon_item, 24, height // 2)
        row.coords(title_item, 52, height // 2)
        row.coords(chevron_item, width - 18, height // 2)

    def set_hover(value):
        if row_state["hover"] == value:
            return
        row_state["hover"] = value
        redraw()

    row.bind("<Configure>", redraw, add="+")
    row.bind("<Enter>", lambda _e: set_hover(True), add="+")
    row.bind("<Leave>", lambda _e: set_hover(False), add="+")
    row.bind("<Button-1>", lambda _e: command(), add="+")

    redraw()
    return row


def show_account_info_window(root):
    show_placeholder(root, "계정 정보", "계정 정보 기능은 추후 제공될 예정입니다.")


def show_workspace_designation_window(app, parent_win=None):
    _ = app
    parent = parent_win if parent_win is not None else getattr(app, "root", app)
    show_placeholder(parent, "워크스페이스 설정", "워크스페이스 지정 화면은 다음 백엔드 단계에서 연결될 예정이에요.")

def show_mapped_drives_window(root):
    mapped_entries = get_mapped_network_drives()
    if mapped_entries is None:
        messagebox.showerror("매핑 드라이브", "매핑된 드라이브 목록을 읽을 수 없습니다.", parent=root)
        return

    if not mapped_entries:
        messagebox.showinfo("매핑 드라이브", "매핑된 드라이브가 없습니다.", parent=root)
        return

    win = tk.Toplevel(root)
    apply_window_icon(win)
    win.title("매핑된 네트워크 드라이브")
    win.geometry("460x420")
    win.configure(bg="white")
    win.transient(root)

    tk.Label(win, text="매핑된 네트워크 드라이브", font=("TkDefaultFont", 10, "bold"), bg="white").pack(pady=(10, 8))

    frame = tk.Frame(win, bg="white")
    frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    listbox = tk.Listbox(frame, font=("TkDefaultFont", 10), activestyle="none", selectmode="extended")
    listbox.pack(side="left", fill="both", expand=True)

    scroll = ttk.Scrollbar(frame, orient="vertical", command=listbox.yview)
    scroll.pack(side="right", fill="y")
    listbox.configure(yscrollcommand=scroll.set)

    for drive, remote in mapped_entries:
        listbox.insert("end", f"{drive} -> {remote}")

    button_row = tk.Frame(win, bg="white")
    button_row.pack(pady=(0, 12))

    unmap_btn = tk.Button(
        button_row,
        text="선택 드라이브 연결 해제",
        width=20,
        state="disabled",
        bg="#d9d9d9",
        fg="black",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    )
    unmap_btn.pack(side="left")

    tk.Button(
        button_row,
        text="닫기",
        width=14,
        command=win.destroy,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        highlightthickness=0,
        cursor="hand2",
    ).pack(side="left", padx=(8, 0))

    def update_unmap_button(*_):
        has_selection = bool(listbox.curselection())
        if has_selection:
            unmap_btn.config(state="normal", bg="#4caf50", fg="white", activebackground="#43a047")
        else:
            unmap_btn.config(state="disabled", bg="#d9d9d9", fg="black", activebackground="#c0c0c0")

    def unmap_selected_drives():
        selected_indices = list(listbox.curselection())
        if not selected_indices:
            return

        failures = []
        for idx in selected_indices:
            drive, _remote = mapped_entries[idx]
            result = subprocess.run(["net", "use", drive, "/delete", "/y"],
                                     capture_output=True, text=True, encoding="cp949", errors="replace")
            if result.returncode != 0:
                err = result.stderr.strip() or result.stdout.strip() or "알 수 없는 오류"
                failures.append(f"{drive}: {err}")

        if failures:
            messagebox.showerror(
                "드라이브 연결 해제",
                "일부 드라이브 연결 해제에 실패했습니다.\n\n" + "\n".join(failures),
                parent=win,
            )

        refreshed = get_mapped_network_drives()
        if refreshed is None:
            messagebox.showerror("매핑 드라이브", "매핑된 드라이브 목록을 새로고침할 수 없습니다.", parent=win)
            return

        mapped_entries[:] = refreshed
        listbox.delete(0, "end")
        for drive, remote in mapped_entries:
            listbox.insert("end", f"{drive} -> {remote}")

        update_unmap_button()

        if not mapped_entries:
            messagebox.showinfo("매핑 드라이브", "매핑된 드라이브가 없습니다.", parent=win)
            win.destroy()

    listbox.bind("<<ListboxSelect>>", update_unmap_button)
    unmap_btn.config(command=unmap_selected_drives)

def show_change_server_name_dialog(app, parent_win):
    dialog = tk.Toplevel(parent_win)
    dialog.title("서버 이름 변경")
    dialog.geometry("380x190")
    dialog.configure(bg="white")
    dialog.transient(parent_win)

    body = tk.Frame(dialog, bg="white", padx=16, pady=14)
    body.pack(fill="both", expand=True)

    current_name = config.default_server_name.lstrip("\\")
    tk.Label(body, text=f"현재 서버 이름: {current_name or '(없음)'}", bg="white", anchor="w").pack(fill="x", pady=(0, 8))

    tk.Label(body, text="새 서버 이름", bg="white", anchor="w").pack(fill="x")
    new_server_var = tk.StringVar(value="")
    entry = tk.Entry(body, textvariable=new_server_var)
    entry.pack(fill="x", pady=(2, 10))

    button_row = tk.Frame(body, bg="white")
    button_row.pack(fill="x")

    apply_btn = tk.Button(
        button_row,
        text="적용",
        width=12,
        state="disabled",
        bg="#d9d9d9",
        fg="black",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        cursor="hand2",
    )
    apply_btn.pack(side="left")

    tk.Button(
        button_row,
        text="취소",
        width=12,
        bg="#d9d9d9",
        activebackground="#c0c0c0",
        relief="flat",
        bd=0,
        cursor="hand2",
        command=dialog.destroy,
    ).pack(side="left", padx=(8, 0))

    def update_apply_button(*_):
        has_name = bool(new_server_var.get().strip())
        if has_name:
            apply_btn.config(state="normal", bg="#4caf50", fg="white", activebackground="#43a047")
        else:
            apply_btn.config(state="disabled", bg="#d9d9d9", fg="black", activebackground="#c0c0c0")

    def apply_server_name():
        cleaned = new_server_var.get().strip().lstrip("\\")
        if not cleaned:
            return

        if state.active_workspace_drive and app.workspace_drive_mapped_by_app:
            app.workspace_manager.unmap_drive(state.active_workspace_drive)

        config.default_server_name = f"\\\\{cleaned}"
        app.clear_workspace(unmap_if_needed=False)
        messagebox.showinfo("설정", f"서버 이름이 {config.default_server_name}(으)로 변경되었습니다.", parent=dialog)
        dialog.destroy()
        app.show_workspace_selection_screen()

    new_server_var.trace_add("write", update_apply_button)
    apply_btn.config(command=apply_server_name)
    update_apply_button()
    entry.focus_set()


def show_settings_screen(app):
    existing = getattr(app, "_settings_window", None)
    if existing is not None and existing.winfo_exists():
        existing.deiconify()
        existing.lift()
        existing.focus_force()
        return

    settings_win = tk.Toplevel(app.root)
    apply_window_icon(settings_win)
    settings_win.title("애플망고 DMS - 설정")
    settings_win.geometry(f"{SETTINGS_WINDOW_WIDTH}x{SETTINGS_WINDOW_HEIGHT}")
    settings_win.minsize(SETTINGS_WINDOW_MIN_WIDTH, SETTINGS_WINDOW_MIN_HEIGHT)
    settings_win.configure(bg=SETTINGS_BG)
    settings_win.transient(app.root)

    app._settings_window = settings_win

    def _cleanup_settings_window(event):
        if event.widget is not settings_win:
            return
        if getattr(app, "_settings_window", None) is settings_win:
            app._settings_window = None

    settings_win.bind("<Destroy>", _cleanup_settings_window, add="+")

    bg = tk.Canvas(
        settings_win,
        bg=SETTINGS_BG,
        highlightthickness=0,
        bd=0,
        relief="flat",
    )
    bg.pack(fill="both", expand=True, padx=14, pady=14)

    card_content = tk.Frame(bg, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    card_window_id = bg.create_window(0, 0, window=card_content, anchor="center")

    card_state = {
        "shape": None,
        "width": 0,
        "height": 0,
    }

    def redraw_card(_event=None):
        view_w = max(1, bg.winfo_width())
        view_h = max(1, bg.winfo_height())

        # Keep the rounded card fully inside the visible viewport.
        card_w = min(484, max(320, view_w - 8))
        card_h = min(684, max(360, view_h - 8))

        cx = view_w // 2
        cy = view_h // 2
        x1 = cx - card_w // 2
        y1 = cy - card_h // 2
        x2 = cx + card_w // 2
        y2 = cy + card_h // 2

        if card_state["shape"] is not None:
            bg.delete(card_state["shape"])

        card_state["shape"] = app._smooth_rounded_rect(
            bg,
            x1,
            y1,
            x2,
            y2,
            24,
            fill=SETTINGS_CARD_BG,
            outline=SETTINGS_CARD_BORDER,
            width=1,
            tags=("settingscard",),
        )
        bg.tag_lower(card_state["shape"])

        bg.coords(card_window_id, cx, cy)
        bg.itemconfigure(
            card_window_id,
            width=max(280, card_w - 44),
            height=max(320, card_h - 36),
        )

        card_state["width"] = card_w
        card_state["height"] = card_h

    bg.bind("<Configure>", redraw_card, add="+")

    scroll_shell = tk.Frame(card_content, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    scroll_shell.pack(fill="both", expand=True)

    scroll_canvas = tk.Canvas(
        scroll_shell,
        bg=SETTINGS_CARD_BG,
        highlightthickness=0,
        bd=0,
        relief="flat",
    )
    scroll_canvas.pack(fill="both", expand=True)

    scroll_body = tk.Frame(scroll_canvas, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    scroll_body_id = scroll_canvas.create_window(0, 0, window=scroll_body, anchor="nw")

    def sync_scroll_region(_event=None):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

    def sync_scroll_width(event):
        scroll_canvas.itemconfigure(scroll_body_id, width=event.width)

    scroll_body.bind("<Configure>", sync_scroll_region, add="+")
    scroll_canvas.bind("<Configure>", sync_scroll_width, add="+")

    scroll_state = {
        "target": 0.0,
        "current": 0.0,
        "job": None,
    }

    def get_max_scroll():
        scroll_canvas.update_idletasks()
        scroll_region = scroll_canvas.cget("scrollregion")
        if not scroll_region:
            return 0.0
        _x0, _y0, _x1, y1 = [float(value) for value in str(scroll_region).split()]
        viewport = float(scroll_canvas.winfo_height())
        return max(0.0, y1 - viewport)

    def apply_scroll_offset(offset):
        max_scroll = get_max_scroll()
        if max_scroll <= 0:
            scroll_canvas.yview_moveto(0.0)
            return
        clamped = max(0.0, min(max_scroll, offset))
        scroll_state["current"] = clamped
        scroll_canvas.yview_moveto(clamped / max_scroll)

    def animate_scroll():
        scroll_state["job"] = None
        current = scroll_state["current"]
        target = scroll_state["target"]
        next_value = current + (target - current) * 0.24
        if abs(next_value - target) < 0.6:
            next_value = target
        apply_scroll_offset(next_value)
        if abs(scroll_state["current"] - scroll_state["target"]) >= 0.6:
            scroll_state["job"] = settings_win.after(16, animate_scroll)

    def schedule_scroll_animation():
        if scroll_state["job"] is None:
            scroll_state["job"] = settings_win.after(16, animate_scroll)

    def add_scroll_delta(delta_pixels):
        max_scroll = get_max_scroll()
        if max_scroll <= 0:
            return
        scroll_state["target"] = max(0.0, min(max_scroll, scroll_state["target"] + delta_pixels))
        schedule_scroll_animation()

    def on_mousewheel(event):
        if scroll_body.winfo_reqheight() <= scroll_canvas.winfo_height():
            return "break"
        delta = event.delta
        if delta == 0:
            return "break"
        add_scroll_delta(-delta / 120.0 * 44.0)
        return "break"

    def bind_scroll_gestures(widget):
        widget.bind("<MouseWheel>", on_mousewheel, add="+")
        for child in widget.winfo_children():
            bind_scroll_gestures(child)

    def _cleanup_scroll_jobs(event):
        if event.widget is not settings_win:
            return
        job = scroll_state.get("job")
        if job is not None:
            try:
                settings_win.after_cancel(job)
            except Exception:
                pass
            scroll_state["job"] = None

    settings_win.bind("<Destroy>", _cleanup_scroll_jobs, add="+")

    section_icon_map = {
        "account_section": _load_settings_icon(settings_win, "account_and_security.svg", size=SETTINGS_ICON_SIZE),
        "system_section": _load_settings_icon(settings_win, "system_and_connection.svg", size=SETTINGS_ICON_SIZE),
        "general_section": _load_settings_icon(settings_win, "general_settings.svg", size=SETTINGS_ICON_SIZE),
        "app_section": _load_settings_icon(settings_win, "app_info.svg", size=SETTINGS_ICON_SIZE),
    }

    icon_map = {
        "account": _load_settings_icon(settings_win, "account_info.svg"),
        "delete_credentials": _load_settings_icon(
            settings_win,
            "delete_credentials.svg",
            tint=SETTINGS_TEXT_DANGER,
        ),
        "server": _load_settings_icon(settings_win, "server_settings.svg"),
        "workspace": _load_settings_icon(settings_win, "workspace_settings.svg"),
        "network": _load_settings_icon(settings_win, "network_drive_settings.svg"),
        "theme": _load_settings_icon(settings_win, "theme.svg"),
        "language": _load_settings_icon(settings_win, "languages.svg"),
        "datetime": _load_settings_icon(settings_win, "date_and_time.svg"),
        "version": _load_settings_icon(settings_win, "version_info.svg"),
        "license": _load_settings_icon(settings_win, "license_info.svg"),
    }

    _create_section_heading(
        app,
        scroll_body,
        "계정 및 보안",
        top_pad=2,
        icon_photo=section_icon_map["account_section"],
    )
    account_rows = tk.Frame(scroll_body, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    account_rows.pack(fill="x", padx=(SETTINGS_ROW_SIDE_PAD, SETTINGS_ROW_SIDE_PAD))

    create_settings_row(
        app,
        account_rows,
        title="계정 정보",
        icon_photo=icon_map["account"],
        command=lambda: show_account_info_window(settings_win),
    ).pack(fill="x", pady=4)
    create_settings_row(
        app,
        account_rows,
        title="저장된 로그인 정보 삭제",
        icon_photo=icon_map["delete_credentials"],
        command=lambda: _confirm_clear_saved_credentials(settings_win),
        destructive=True,
    ).pack(fill="x", pady=4)

    _create_section_heading(
        app,
        scroll_body,
        "시스템 및 연결",
        top_pad=24,
        icon_photo=section_icon_map["system_section"],
    )
    system_rows = tk.Frame(scroll_body, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    system_rows.pack(fill="x", padx=(SETTINGS_ROW_SIDE_PAD, SETTINGS_ROW_SIDE_PAD))

    create_settings_row(
        app,
        system_rows,
        title="서버 설정",
        icon_photo=icon_map["server"],
        command=lambda: show_change_server_name_dialog(app, settings_win),
    ).pack(fill="x", pady=4)
    create_settings_row(
        app,
        system_rows,
        title="워크스페이스 설정",
        icon_photo=icon_map["workspace"],
        command=lambda: show_workspace_designation_window(app, settings_win),
    ).pack(fill="x", pady=4)
    create_settings_row(
        app,
        system_rows,
        title="네트워크 드라이브 관리",
        icon_photo=icon_map["network"],
        command=lambda: show_mapped_drives_window(settings_win),
    ).pack(fill="x", pady=4)

    _create_section_heading(
        app,
        scroll_body,
        "일반 설정",
        top_pad=24,
        icon_photo=section_icon_map["general_section"],
    )
    general_rows = tk.Frame(scroll_body, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    general_rows.pack(fill="x", padx=(SETTINGS_ROW_SIDE_PAD, SETTINGS_ROW_SIDE_PAD))

    create_settings_row(
        app,
        general_rows,
        title="테마",
        icon_photo=icon_map["theme"],
        command=lambda: show_placeholder(settings_win, "테마", "테마 설정 기능은 추후 제공될 예정이에요."),
    ).pack(fill="x", pady=4)
    create_settings_row(
        app,
        general_rows,
        title="언어",
        icon_photo=icon_map["language"],
        command=lambda: show_placeholder(settings_win, "언어", "언어 설정 기능은 추후 제공될 예정이에요."),
    ).pack(fill="x", pady=4)
    create_settings_row(
        app,
        general_rows,
        title="날짜 및 시간",
        icon_photo=icon_map["datetime"],
        command=lambda: show_placeholder(settings_win, "날짜 및 시간", "날짜 및 시간 형식 설정은 추후 제공될 예정이에요."),
    ).pack(fill="x", pady=4)

    _create_section_heading(
        app,
        scroll_body,
        "앱 정보",
        top_pad=24,
        icon_photo=section_icon_map["app_section"],
    )
    app_info_rows = tk.Frame(scroll_body, bg=SETTINGS_CARD_BG, highlightthickness=0, bd=0)
    app_info_rows.pack(fill="x", padx=(SETTINGS_ROW_SIDE_PAD, SETTINGS_ROW_SIDE_PAD), pady=(0, 4))

    create_settings_row(
        app,
        app_info_rows,
        title="버전 정보",
        icon_photo=icon_map["version"],
        command=lambda: show_placeholder(settings_win, "버전 정보", "버전 정보 화면은 추후 연결될 예정이에요."),
    ).pack(fill="x", pady=4)
    create_settings_row(
        app,
        app_info_rows,
        title="라이선스 정보",
        icon_photo=icon_map["license"],
        command=lambda: show_placeholder(settings_win, "라이선스 정보", "라이선스 정보 화면은 추후 연결될 예정이에요."),
    ).pack(fill="x", pady=4)

    bind_scroll_gestures(card_content)

    settings_win.update_idletasks()
    _center_toplevel_to_parent(app.root, settings_win)
    redraw_card()