import tkinter as tk

import applemango_dms.state as state


def show_main_workspace_menu(app):
    if not state.active_workspace:
        app.show_workspace_selection_screen()
        return

    app.show_save_files_screen()


def show_workspace_exit_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 워크스페이스 나가기")

    app._build_sidebar_nav(
        shell["sidebar"],
        "exit",
        [
            ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", app.show_save_files_screen, "#2d6cdf"),
            ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", app.show_search_files_screen, "#111111"),
            ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", app.show_workspace_exit_screen, "#d33e3e"),
        ],
        icon_photos={
            "save": app.ui_icon_photos.get("workspace_file_save"),
            "search": app.ui_icon_photos.get("workspace_file_search"),
            "exit": app.ui_icon_photos.get("workspace_exit"),
        },
    )

    outer = shell["content"]
    app._build_workspace_page_header(outer, "워크스페이스 나가기", "현재 작업을 마치고 워크스페이스 목록으로 돌아갑니다.")

    action_row = tk.Frame(outer, bg="#ffffff")
    action_row.pack(fill="x", padx=20, pady=(4, 0))
    tk.Button(
        action_row,
        text="나가기",
        width=14,
        bg="#d33e3e",
        fg="white",
        activebackground="#bf3232",
        relief="flat",
        bd=0,
        cursor="hand2",
        command=app.show_workspace_selection_screen,
    ).pack(side="left")
