import tkinter as tk
from applemango_dms.ui import colors

HC_BG = colors.BACKGROUND

def build_header_controls(app, parent, context, bg=HC_BG):
    container = tk.Frame(parent, bg=bg, bd=0, highlightthickness=0)

    def make_icon_button(
        icon_key,
        fallback_text,
        command,
        *,
        hover_bg="#eef2fb",
        fg="#111111",
        padding=(7, 7),
        hover_icon_key=None,
    ):
        wrapper = tk.Frame(container, bg=bg, bd=0, highlightthickness=0)
        icon_photo = app.ui_icon_photos.get(icon_key)
        hover_icon = app.ui_icon_photos.get(hover_icon_key) if hover_icon_key else None

        label = tk.Label(
            wrapper,
            image=icon_photo,
            text=fallback_text if icon_photo is None else "",
            bg=bg,
            fg=fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        label.pack(padx=padding[0], pady=padding[1])

        def set_state(active_bg, *, use_hover_icon=False):
            wrapper.configure(bg=active_bg)
            label.configure(bg=active_bg)
            if hover_icon is not None and icon_photo is not None:
                label.configure(image=hover_icon if use_hover_icon else icon_photo)

        def on_enter(_event=None):
            set_state(hover_bg, use_hover_icon=True)

        def on_leave(_event=None):
            set_state(bg, use_hover_icon=False)

        def activate(_event=None):
            command()

        for widget in (wrapper, label):
            widget.bind("<Button-1>", activate, add="+")
            widget.bind("<Enter>", on_enter, add="+")
            widget.bind("<Leave>", on_leave, add="+")

        wrapper._icon_label = label
        wrapper._fg = fg
        set_state(bg, use_hover_icon=False)
        return wrapper

    make_icon_button(
        "header_settings",
        "S",
        app.show_settings_screen,
        hover_bg="#eef2fb",
        fg="#111111",
    ).pack(side="left", padx=(4, 0))

    if context == "workspace_selection":
        make_icon_button(
            "header_logout",
            "L",
            app.logout_and_return_to_login,
            hover_bg="#eef2fb",
            fg="#111111",
        ).pack(side="left", padx=(4, 0))
    elif context == "workspace":
        make_icon_button(
            "header_home",
            "H",
            app.leave_workspace_to_selection,
            hover_bg="#eef2fb",
            fg="#111111",
        ).pack(side="left", padx=(4, 0))

    window_cluster = tk.Frame(container, bg=bg, bd=0, highlightthickness=0)

    divider_label = tk.Label(
        window_cluster,
        text="|",
        bg=bg,
        fg="#111111",
        font=app._font(9, "bold"),
    )
    divider_label.pack(side="left", padx=(6, 8))

    minimize_btn = make_icon_button(
        "window_minimize",
        "_",
        lambda: app.root.iconify(),
        hover_bg="#eef2fb",
        fg="#111111",
    )
    minimize_btn.pack(in_=window_cluster, side="left", padx=(4, 0))

    fullscreen_btn = make_icon_button(
        "window_fullscreen_exit" if app.is_fullscreen() else "window_fullscreen_enter",
        "[]",
        app.toggle_fullscreen,
        hover_bg="#eef2fb",
        fg="#111111",
    )
    fullscreen_btn.pack(in_=window_cluster, side="left", padx=(4, 0))

    close_btn = make_icon_button(
        "window_close",
        "X",
        app.exit_application,
        hover_bg="#fff1f1",
        fg="#111111",
        hover_icon_key="window_close_hover",
    )
    close_btn.pack(in_=window_cluster, side="left", padx=(4, 0))

    def refresh_controls():
        key = "window_fullscreen_exit" if app.is_fullscreen() else "window_fullscreen_enter"
        photo = app.ui_icon_photos.get(key)
        label = fullscreen_btn._icon_label
        if photo is not None:
            label.configure(image=photo, text="")
        else:
            label.configure(image="", text=("[]" if app.is_fullscreen() else "<>"), fg=fullscreen_btn._fg)

        if app.is_fullscreen():
            if not window_cluster.winfo_manager():
                window_cluster.pack(side="left")
        else:
            if window_cluster.winfo_manager():
                window_cluster.pack_forget()

    app.register_window_controls_refresher(refresh_controls)
    refresh_controls()

    return container

def build_window_controls(app, parent, bg=HC_BG):
    return build_header_controls(app, parent, context="workspace", bg=bg)