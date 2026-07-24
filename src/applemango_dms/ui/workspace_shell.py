import tkinter as tk

import applemango_dms.state as state

from applemango_dms.ui.header_controls import build_header_controls


def create_workspace_shell(app):
    app._resize(1372, 900)
    app.root.title("애플망고 DMS - 워크스페이스")
    app.clear_screen()
    app.root.configure(bg="#ffffff")

    bg = tk.Canvas(app.root, bg="#ffffff", highlightthickness=0, bd=0)
    bg.pack(fill="both", expand=True)

    main_card = app.create_card(
        bg,
        width=1272,
        height=798,
        fill_top="#ffffff",
        fill_bottom="#f4f7ff",
        radius=20,
    )
    content = main_card["content"]
    redraw = main_card["redraw"]

    def on_bg_resize(event):
        redraw(event.width // 2, event.height // 2)

    bg.bind("<Configure>", on_bg_resize)

    content.configure(bg="#ffffff")
    shell = tk.Frame(content, bg="#ffffff")
    shell.pack(fill="both", expand=True)

    header = tk.Frame(shell, bg="#ffffff", highlightthickness=0, bd=0)
    header.pack(fill="x", pady=(0, 0))

    left = tk.Frame(header, bg="#ffffff", padx=20, pady=14)
    left.pack(side="left", fill="x", expand=True)

    workspace_name = state.active_workspace or "워크스페이스"

    workspace_folder_icon = app.ui_icon_photos.get("workspace_folder")
    if workspace_folder_icon is not None:
        folder_label = tk.Label(left, image=workspace_folder_icon, bg="#ffffff")
        folder_label.image = workspace_folder_icon
        folder_label.pack(side="left", padx=(0, 12), pady=(2, 0), anchor="n")
    else:
        tk.Label(left, text="\U0001F4C1", font=("Segoe UI Emoji", 19), fg="#2fa44f", bg="#ffffff").pack(side="left", padx=(0, 12), pady=(2, 0), anchor="n")
    title_block = tk.Frame(left, bg="#ffffff")
    title_block.pack(side="left", fill="x", expand=True)
    tk.Label(title_block, text=workspace_name, font=app._font(20, "bold"), fg="#1f2b4a", bg="#ffffff", anchor="w").pack(anchor="w", pady=(0, 0))

    right = tk.Frame(header, bg="#ffffff", padx=20, pady=14)
    right.pack(side="right", anchor="ne")
    controls = build_header_controls(app, right, context="workspace", bg="#ffffff")
    controls.pack(anchor="e")

    body = tk.Frame(shell, bg="#ffffff")
    body.pack(fill="both", expand=True)

    sidebar_shell = tk.Canvas(body, bg="#ffffff", width=225, highlightthickness=0, bd=0)
    sidebar_shell.pack(side="left", fill="y", padx=(12, 0), pady=(10, 12))

    sidebar = tk.Frame(sidebar_shell, bg="#ffffff")
    sidebar_window_id = sidebar_shell.create_window(0, 0, window=sidebar, anchor="nw")

    def redraw_sidebar(_event=None):
        sidebar_shell.delete("sidepanel")
        width = max(170, sidebar_shell.winfo_width())
        height = max(220, sidebar_shell.winfo_height())
        app._smooth_rounded_rect(
            sidebar_shell,
            1,
            1,
            width - 1,
            height - 1,
            24,
            fill="#ffffff",
            outline="#dfe5ee",
            width=1,
            tags="sidepanel",
        )
        sidebar_shell.coords(sidebar_window_id, 6, 6)
        sidebar_shell.itemconfigure(sidebar_window_id, width=max(10, width - 12), height=max(10, height - 12))
        sidebar_shell.tag_lower("sidepanel")

    sidebar_shell.bind("<Configure>", redraw_sidebar)

    content_area = tk.Frame(body, bg="#ffffff", highlightthickness=0, bd=0)
    content_area.pack(side="left", fill="both", expand=True)

    return {
        "bg": bg,
        "card": main_card,
        "content": content_area,
        "sidebar": sidebar,
        "shell": shell,
        "header": header,
        "body": body,
    }


def build_workspace_page_header(app, parent, title, subtitle):
    header = tk.Frame(parent, bg="#ffffff")
    header.pack(fill="x", padx=20, pady=(16, 12))
    tk.Label(header, text=title, font=app._font(17, "bold"), fg="#1f2540", bg="#ffffff", anchor="w").pack(fill="x", pady=(0, 4))
    tk.Label(header, text=subtitle, font=app._font(12), fg="#1f2540", bg="#ffffff", anchor="w").pack(fill="x")
    return header
