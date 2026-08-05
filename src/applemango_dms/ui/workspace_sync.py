import tkinter as tk

from applemango_dms.ui import colors
from applemango_dms.ui.workplace_menu import render_workspace_sidebar_nav

SYNC_SURFACE = colors.SURFACE_ALT
SYNC_TEXT_SECONDARY = colors.TEXT_SECONDARY


def show_sync_workspace_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 워크스페이스 동기화")

    render_workspace_sidebar_nav(app, shell["sidebar"], "sync")

    outer = shell["content"]
    app._build_workspace_page_header(outer, "워크스페이스 동기화", "NAS 워크스페이스와 DMS 데이터베이스를 동기화해요.")

    board = tk.Frame(outer, bg=SYNC_SURFACE, highlightthickness=0, bd=0)
    board.pack(fill="both", expand=True, padx=0, pady=0)

    content = tk.Frame(board, bg=SYNC_SURFACE)
    content.pack(fill="both", expand=True, padx=24, pady=24)

    tk.Label(
        content,
        text="동기화 기능 안내 문구 Placeholder",
        font=app._font(12),
        fg=SYNC_TEXT_SECONDARY,
        bg=SYNC_SURFACE,
        anchor="w",
    ).pack(anchor="w")