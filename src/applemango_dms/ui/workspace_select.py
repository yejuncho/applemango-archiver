import threading
import tkinter as tk
from tkinter import messagebox

import applemango_dms.config as config
import applemango_dms.state as state

from applemango_dms.services.nas import discover_server_shares
from applemango_dms.ui.widgets import WorkspaceStack
from applemango_dms.ui.header_controls import build_header_controls

def show_workspace_selection_screen(app):
    app._stop_login_connectivity_polling()
    if state.active_workspace_drive and app.workspace_drive_mapped_by_app:
        app.workspace_manager.unmap_drive(state.active_workspace_drive)
    state.active_workspace = ""
    state.active_workspace_drive = ""
    app.workspace_drive_mapped_by_app = False

    app._center_window(760, 680)
    app.root.title("애플망고 DMS - 워크스페이스 선택")
    app.clear_screen()
    app.root.configure(bg="#ffffff")

    if state.is_demo_mode:
        shares = app._load_demo_workspace_names()
    else:
        shares = discover_server_shares(config.default_server_name)

    bg = tk.Canvas(app.root, bg="#ffffff", highlightthickness=0, bd=0)
    bg.pack(fill="both", expand=True)

    main_card = app.create_card(
        bg,
        width=702,
        height=596,
        fill_top="#ffffff",
        fill_bottom="#ffffff",
    )
    content = main_card["content"]
    redraw = main_card["redraw"]

    def on_bg_resize(event):
        redraw(event.width // 2, event.height // 2)

    bg.bind("<Configure>", on_bg_resize)

    content.configure(bg="#ffffff")
    container = tk.Frame(content, bg="#ffffff")
    container.pack(fill="both", expand=True)

    header_row = tk.Frame(container, bg="#ffffff")
    header_row.pack(fill="x", pady=(0, 18))

    left_header = tk.Frame(header_row, bg="#ffffff")
    left_header.pack(side="left", fill="x", expand=True)

    display_name = state.session_account_name or state.session_username or "사용자"
    tk.Label(
        left_header,
        text=f"환영합니다, {display_name}님",
        font=app._font(20, "bold"),
        fg="#06012a",
        bg="#ffffff",
        anchor="w",
    ).pack(anchor="w")
    tk.Label(
        left_header,
        text="워크스페이스를 선택해주세요.",
        font=app._font(12),
        fg="#000000",
        bg="#ffffff",
        anchor="w",
    ).pack(anchor="w", pady=(6, 0))

    right_header = tk.Frame(header_row, bg="#ffffff", bd=0, highlightthickness=0)
    right_header.pack(side="right", anchor="ne")

    button_row = tk.Frame(right_header, bg="#ffffff")
    button_row.pack(anchor="e")
    controls = build_header_controls(app, button_row, context="workspace_selection", bg="#ffffff")
    controls.pack(side="left")

    list_shell = tk.Canvas(container, bg="#ffffff", highlightthickness=0, bd=0)
    list_shell.pack(fill="both", expand=True)

    stack_surface = tk.Frame(list_shell, bg="#ffffff")
    surface_window = list_shell.create_window(0, 0, window=stack_surface, anchor="nw")

    stack_canvas = tk.Canvas(stack_surface, bg="#ffffff", highlightthickness=0, bd=0)
    stack_canvas.pack(side="left", fill="both", expand=True, padx=(0, 2), pady=(2, 0))

    def enter_workspace(selected):
        if state.is_demo_mode:
            app.set_workspace(selected, "", False)
        else:
            drive, mapped_by_app, err = app.workspace_manager.map_workspace(selected, state.session_username, state.session_password)
            if not drive:
                messagebox.showerror("워크스페이스", f"워크스페이스 드라이브 매핑에 실패했습니다:\n{err}", parent=app.root)
                return
            app.set_workspace(selected, drive, mapped_by_app)
        app.show_main_workspace_menu()

    if not shares:
        empty_label = tk.Label(
            stack_surface,
            text="선택 가능한 워크스페이스가 없습니다.",
            bg="#ffffff",
            fg="#666666",
            font=app._font(11),
            anchor="w",
        )
        empty_label.pack(anchor="w", padx=24, pady=24)
        workspace_stack = None
    else:
        workspace_stack = WorkspaceStack(
            stack_canvas,
            shares,
            on_open=enter_workspace,
            bg="#ffffff",
            card_bg="#ffffff",
            meta_icon_photos={
                "clock": app.ui_icon_photos.get("workspace_clock"),
                "database": app.ui_icon_photos.get("workspace_database"),
                "file_stack": app.ui_icon_photos.get("workspace_file_stack"),
            },
            folder_icon_photo=app.ui_icon_photos.get("workspace_selection_folder"),
            font_family=app.ui_font_family,
        )
        stack_body_id = stack_canvas.create_window((0, 0), window=workspace_stack, anchor="nw")
        scroll_state = {
            "target": 0.0,
            "current": 0.0,
            "job": None,
            "dragging": False,
            "last_y": None,
            "moved": False,
        }

        def sync_stack_region(total_height=None):
            body_height = total_height if total_height is not None else workspace_stack.winfo_reqheight()
            stack_canvas.configure(scrollregion=(0, 0, stack_canvas.winfo_width(), body_height + 12))

        def get_max_scroll():
            stack_canvas.update_idletasks()
            scroll_region = stack_canvas.cget("scrollregion")
            if not scroll_region:
                return 0.0
            _x0, _y0, _x1, y1 = [float(value) for value in str(scroll_region).split()]
            viewport = float(stack_canvas.winfo_height())
            return max(0.0, y1 - viewport)

        def apply_scroll_offset(offset):
            max_scroll = get_max_scroll()
            if max_scroll <= 0:
                stack_canvas.yview_moveto(0.0)
                return
            clamped = max(0.0, min(max_scroll, offset))
            scroll_state["current"] = clamped
            stack_canvas.yview_moveto(clamped / max_scroll)

        def animate_scroll():
            scroll_state["job"] = None
            current = scroll_state["current"]
            target = scroll_state["target"]
            next_value = current + (target - current) * 0.24
            if abs(next_value - target) < 0.6:
                next_value = target
            apply_scroll_offset(next_value)
            if abs(scroll_state["current"] - scroll_state["target"]) >= 0.6:
                scroll_state["job"] = app.root.after(16, animate_scroll)

        def schedule_scroll_animation():
            if scroll_state["job"] is None:
                scroll_state["job"] = app.root.after(16, animate_scroll)

        def add_scroll_delta(delta_pixels):
            max_scroll = get_max_scroll()
            if max_scroll <= 0:
                return
            scroll_state["target"] = max(0.0, min(max_scroll, scroll_state["target"] + delta_pixels))
            schedule_scroll_animation()

        def on_stack_mousewheel(event):
            delta = event.delta
            if delta == 0:
                return "break"
            add_scroll_delta(-delta / 120.0 * 44.0)
            return "break"

        def on_drag_press(event):
            scroll_state["dragging"] = True
            scroll_state["last_y"] = event.y_root
            scroll_state["moved"] = False

        def on_drag_motion(event):
            if not scroll_state["dragging"] or scroll_state["last_y"] is None:
                return
            delta_y = event.y_root - scroll_state["last_y"]
            scroll_state["last_y"] = event.y_root
            if abs(delta_y) > 0:
                scroll_state["moved"] = True
                add_scroll_delta(-delta_y * 1.35)

        def on_drag_release(_event):
            scroll_state["dragging"] = False
            scroll_state["last_y"] = None
            app.root.after(0, lambda: scroll_state.__setitem__("moved", False))

        def bind_scroll_gestures(widget):
            widget.bind("<MouseWheel>", on_stack_mousewheel, add="+")
            widget.bind("<ButtonPress-1>", on_drag_press, add="+")
            widget.bind("<B1-Motion>", on_drag_motion, add="+")
            widget.bind("<ButtonRelease-1>", on_drag_release, add="+")
            for child in widget.winfo_children():
                bind_scroll_gestures(child)

        workspace_stack.on_layout = lambda height: sync_stack_region(height)

        def on_stack_configure(event):
            stack_canvas.itemconfigure(stack_body_id, width=int(event.width * 0.91))
            stack_canvas.coords(stack_body_id, max(0, int((event.width - (event.width * 0.91)) / 2)), 0)
            sync_stack_region()
            apply_scroll_offset(scroll_state["current"])

        stack_canvas.bind("<Configure>", on_stack_configure)
        bind_scroll_gestures(workspace_stack)
        bind_scroll_gestures(stack_canvas)

        for workspace_name in shares:
            cached_meta = app.workspace_metadata_cache.get(workspace_name)
            if cached_meta:
                workspace_stack.set_card_metadata(workspace_name, cached_meta)

    def redraw_list_shell(_event=None):
        width = max(200, list_shell.winfo_width())
        height = max(200, list_shell.winfo_height())
        list_shell.itemconfigure(surface_window, width=max(180, width - 6), height=max(180, height - 2))
        list_shell.coords(surface_window, 0, 0)
        list_shell.tag_raise(surface_window)

    list_shell.bind("<Configure>", redraw_list_shell)

    to_load = [name for name in shares if name not in app.workspace_metadata_cache]
    if not to_load:
        return

    def load_metadata_worker(workspace_names):
        for workspace_name in workspace_names:
            try:
                meta = app._build_workspace_metadata(workspace_name)
            except Exception:
                meta = {
                    "last_modified": "정보 없음",
                    "size_text": "0.0 MB",
                    "file_count": 0,
                }
            app.workspace_metadata_cache[workspace_name] = meta

            def apply_metadata(name=workspace_name, metadata=meta):
                if workspace_stack and workspace_stack.winfo_exists():
                    workspace_stack.set_card_metadata(name, metadata)

            app.root.after(0, apply_metadata)

    threading.Thread(target=load_metadata_worker, args=(to_load,), daemon=True).start()