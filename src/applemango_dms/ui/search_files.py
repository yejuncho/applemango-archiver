import tkinter as tk
from applemango_dms.ui.workplace_menu import build_sidebar_nav

from applemango_dms.ui import colors

SF_SURFACE = colors.SURFACE_ALT
SF_STATUS_PROCESSING = colors.PROCESSING
SF_TEXT_DARK = colors.TEXT_NEUTRAL_DARK
SF_STATUS_FAILED = colors.FAILED_STRONG

def show_search_files_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 파일 검색")

    build_sidebar_nav(
        app,
        shell["sidebar"],
        "search",
        [
            ("save", "\U0001F4E4", "파일 저장", "새 파일을 업로드하거나\n기존 파일을 저장합니다.", app.show_save_files_screen, SF_STATUS_PROCESSING),
            ("search", "\U0001F50D", "파일 검색", "저장한 파일을 검색하고\n열람합니다.", app.show_search_files_screen, SF_TEXT_DARK),
            ("exit", "\u21a9", "워크스페이스 나가기", "현재 워크스페이스를 나가고\n목록으로 돌아갑니다.", app.show_workspace_exit_screen, SF_STATUS_FAILED),
        ],
        icon_photos={
            "save": app.ui_icon_photos.get("workspace_file_save"),
            "search": app.ui_icon_photos.get("workspace_file_search"),
            "exit": app.ui_icon_photos.get("workspace_exit"),
        },
    )

    outer = shell["content"]
    app._build_workspace_page_header(outer, "파일 검색", "다양한 조건으로 파일을 검색할 수 있습니다.")

    placeholder = tk.Frame(outer, bg=SF_SURFACE, highlightthickness=0)
    placeholder.pack(fill="both", expand=True, padx=20, pady=(0, 20))