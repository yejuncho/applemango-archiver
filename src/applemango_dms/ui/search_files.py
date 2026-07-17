import os
import re
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from applemango_dms.ui.workplace_menu import build_sidebar_nav

import applemango_dms.state as state

def show_search_files_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 파일 검색")

    build_sidebar_nav(
        app,
        shell["sidebar"],
        "search",
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
    app._build_workspace_page_header(outer, "파일 검색", "다양한 조건으로 파일을 검색할 수 있습니다.")

    scroll_canvas = tk.Canvas(outer, bg="#ffffff", highlightthickness=0)
    scroll_canvas.pack(fill="both", expand=True)

    inner = tk.Frame(scroll_canvas, bg="#ffffff", padx=20, pady=0)
    inner_id = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_resize(_event):
        scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))
        scroll_canvas.itemconfigure(inner_id, width=scroll_canvas.winfo_width())

    inner.bind("<Configure>", _on_inner_resize)
    scroll_canvas.bind("<Configure>", lambda e: scroll_canvas.itemconfigure(inner_id, width=e.width))
    scroll_canvas.bind("<MouseWheel>", lambda e: scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    workspace_var = tk.StringVar(value=state.active_workspace)
    workspace_id = getattr(state, "active_workspace_id", None)
    date_entry_var = tk.StringVar(value="")
    doc_type_var = tk.StringVar(value="전체")
    tags_var = tk.StringVar(value="")
    free_var = tk.StringVar(value="")
    app._bind_iso_date_formatter(date_entry_var)

    if workspace_id is None:
        raise RuntimeError("No active workspace ID is available.")

    document_type_records = app.db.get_document_types(workspace_id)
    document_type_options = [record["name"] for record in document_type_records]

    def _parse_date_input():
        parts = date_entry_var.get().strip().split("-")
        year = parts[0].strip() if len(parts) > 0 else ""
        month = parts[1].strip() if len(parts) > 1 else ""
        day = parts[2].strip() if len(parts) > 2 else ""
        return year, month, day

    def _build_date_prefix():
        year, month, day = _parse_date_input()
        if not year:
            return None
        if not re.fullmatch(r"\d{4}", year):
            raise ValueError("연도는 4자리(YYYY)여야 합니다.")
        if month:
            if not month.isdigit() or not (1 <= int(month) <= 12):
                raise ValueError("월은 01-12 범위여야 합니다.")
            month = f"{int(month):02d}"
        if day:
            if not month:
                raise ValueError("일을 입력하려면 월을 먼저 입력하세요.")
            if not day.isdigit() or not (1 <= int(day) <= 31):
                raise ValueError("일은 01-31 범위여야 합니다.")
            day = f"{int(day):02d}"
        if year and month and day:
            return f"{year}-{month}-{day}"
        if year and month:
            return f"{year}-{month}"
        return year

    filters = tk.Frame(inner, bg="#fbfbff", highlightthickness=1, highlightbackground="#e6eaf4", padx=10, pady=8)
    filters.pack(fill="x", pady=(0, 10))

    tk.Label(filters, text="워크스페이스", bg="#fbfbff", width=16, anchor="w").grid(row=0, column=0, sticky="w", pady=3)
    tk.Entry(filters, textvariable=workspace_var, width=36, state="readonly").grid(row=0, column=1, columnspan=3, sticky="w", pady=3)

    tk.Label(filters, text="날짜 (YYYY-MM-DD)", bg="#fbfbff", width=16, anchor="w").grid(row=1, column=0, sticky="w", pady=3)
    tk.Entry(filters, textvariable=date_entry_var, width=16).grid(row=1, column=1, sticky="w", pady=3)
    tk.Label(filters, text="예: 2024-06-15 또는 2024-06 또는 2024",
         bg="#fbfbff", fg="#888888", font=app._font(8)).grid(row=1, column=2, columnspan=2, sticky="w", padx=(6, 0))

    tk.Label(filters, text="문서 유형", bg="#fbfbff", width=16, anchor="w").grid(row=2, column=0, sticky="w", pady=3)
    ttk.Combobox(filters, textvariable=doc_type_var,
             values=["전체"] + document_type_options,
                 state="readonly", width=24).grid(row=2, column=1, sticky="w", pady=3)

    tk.Label(filters, text="태그", bg="#fbfbff", width=16, anchor="w").grid(row=3, column=0, sticky="w", pady=3)
    tk.Entry(filters, textvariable=tags_var, width=42).grid(row=3, column=1, columnspan=3, sticky="w", pady=3)

    tk.Label(filters, text="자유 검색어", bg="#fbfbff", width=16, anchor="w").grid(row=4, column=0, sticky="w", pady=3)
    tk.Entry(filters, textvariable=free_var, width=42).grid(row=4, column=1, columnspan=3, sticky="w", pady=3)

    filter_btn_row = tk.Frame(filters, bg="#fbfbff")
    filter_btn_row.grid(row=5, column=0, columnspan=5, sticky="w", pady=(8, 2))

    search_btn = tk.Button(filter_btn_row, text="검색", width=12,
                           bg="#4a556f", fg="white", activebackground="#3f485f",
                           relief="flat", bd=0, highlightthickness=0, cursor="hand2")
    search_btn.pack(side="left")

    clear_btn = tk.Button(filter_btn_row, text="초기화", width=12,
                          bg="#d9d9d9", activebackground="#c0c0c0",
                          relief="flat", bd=0, highlightthickness=0, cursor="hand2")
    clear_btn.pack(side="left", padx=(8, 0))

    results_frame = tk.Frame(inner, bg="#fbfbff", highlightthickness=1, highlightbackground="#e6eaf4", padx=4, pady=6)
    results_frame.pack(fill="x", pady=(0, 10))

    cols = ("archive_date", "document_type", "tags", "archived_filename", "uploaded_by", "size", "full_path")
    table = ttk.Treeview(results_frame, columns=cols, show="headings", height=14, selectmode="extended")
    table.heading("archive_date", text="보관 날짜")
    table.heading("document_type", text="문서 유형")
    table.heading("tags", text="태그")
    table.heading("archived_filename", text="저장 파일명")
    table.heading("uploaded_by", text="업로드 사용자")
    table.heading("size", text="크기")
    table.heading("full_path", text="전체 경로")

    table.column("archive_date", width=95, anchor="w", minwidth=80)
    table.column("document_type", width=110, anchor="w", minwidth=90)
    table.column("tags", width=140, anchor="w", minwidth=100)
    table.column("archived_filename", width=200, anchor="w", minwidth=150)
    table.column("uploaded_by", width=100, anchor="w", minwidth=80)
    table.column("size", width=80, anchor="e", minwidth=60)
    table.column("full_path", width=320, anchor="w", minwidth=200)
    table.grid(row=0, column=0, sticky="nsew")

    ytable_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=table.yview)
    ytable_scroll.grid(row=0, column=1, sticky="ns")
    table.configure(yscrollcommand=ytable_scroll.set)

    xtable_scroll = ttk.Scrollbar(results_frame, orient="horizontal", command=table.xview)
    xtable_scroll.grid(row=1, column=0, sticky="ew")
    table.configure(xscrollcommand=xtable_scroll.set)

    results_frame.grid_rowconfigure(0, weight=1)
    results_frame.grid_columnconfigure(0, weight=1)

    action_row = tk.Frame(inner, bg="#fbfbff")
    action_row.pack(fill="x", pady=(0, 8))

    open_file_btn = tk.Button(action_row, text="파일 열기", width=14,
                              bg="#d9d9d9", fg="black", activebackground="#c0c0c0",
                              relief="flat", bd=0, cursor="hand2")
    open_file_btn.pack(side="left")

    delete_file_btn = tk.Button(action_row, text="파일 삭제", width=14,
                                bg="#d9d9d9", fg="black", activebackground="#c0c0c0",
                                relief="flat", bd=0, cursor="hand2")
    delete_file_btn.pack(side="left", padx=(8, 0))

    tk.Button(action_row, text="새로고침", width=12, bg="#d9d9d9", activebackground="#c0c0c0",
              relief="flat", bd=0, cursor="hand2",
              command=lambda: run_search()).pack(side="left", padx=(8, 0))

    tk.Button(action_row, text="뒤로", width=12, bg="#d9d9d9", activebackground="#c0c0c0",
              relief="flat", bd=0, cursor="hand2",
              command=app.show_main_workspace_menu).pack(side="left", padx=(8, 0))

    def clear_results():
        table.delete(*table.get_children())

    def run_search():
        clear_results()
        if not state.active_workspace or workspace_id is None:
            messagebox.showerror("파일 검색", "활성 워크스페이스가 없습니다.", parent=app.root)
            return
        try:
            date_prefix = _build_date_prefix()
        except ValueError as exc:
            messagebox.showerror("파일 검색", str(exc), parent=app.root)
            return

        app.db.audit_missing_files(workspace_id)

        rows = app.db.search_files(
            workspace_id=workspace_id,
            date_prefix=date_prefix,
            document_type=doc_type_var.get(),
            tags=tags_var.get().strip(),
            free_text=free_var.get().strip(),
        )

        for idx, row in enumerate(rows):
            archive_date, document_type, tags, archived_filename, uploaded_by, file_size, full_path = row
            size_text = f"{int(file_size):,}" if isinstance(file_size, int) else str(file_size or "")
            table.insert("", "end", iid=f"r{idx}",
                         values=(archive_date, document_type, tags, archived_filename,
                                 uploaded_by, size_text, full_path))
        _update_action_buttons()

    def clear_filters_only():
        date_entry_var.set("")
        doc_type_var.set("전체")
        tags_var.set("")
        free_var.set("")

    def _get_selected_paths():
        return [table.item(iid, "values")[6] for iid in table.selection() if table.item(iid, "values")]

    def _update_action_buttons(*_):
        has_selection = bool(table.selection())
        if has_selection:
            open_file_btn.config(bg="#4a556f", fg="white", activebackground="#3f485f")
            delete_file_btn.config(bg="#4a556f", fg="white", activebackground="#3f485f")
        else:
            open_file_btn.config(bg="#d9d9d9", fg="black", activebackground="#c0c0c0")
            delete_file_btn.config(bg="#d9d9d9", fg="black", activebackground="#c0c0c0")

    def open_files():
        paths = _get_selected_paths()
        if not paths:
            return
        for target in paths:
            path = Path(target)
            if not path.exists():
                messagebox.showerror("파일 열기", f"파일을 찾을 수 없습니다:\n{target}", parent=app.root)
                continue
            try:
                os.startfile(str(path))
            except OSError as exc:
                messagebox.showerror("파일 열기", str(exc), parent=app.root)

    def delete_files():
        paths = _get_selected_paths()
        if not paths:
            return
        count = len(paths)
        names = "\n".join(Path(p).name for p in paths[:10])
        if count > 10:
            names += f"\n... 외 {count - 10}개"
        confirmed = messagebox.askyesno(
            "파일 삭제",
            f"정말로 {count}개 파일을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.\n\n{names}",
            parent=app.root,
        )
        if not confirmed:
            return
        errors = []
        deleted_paths = []
        for target in paths:
            path = Path(target)
            try:
                path.unlink()
                deleted_paths.append(str(path))
            except FileNotFoundError:
                errors.append(f"{path.name}: 파일이 이미 존재하지 않습니다.")
            except OSError as exc:
                errors.append(f"{path.name}: {exc}")
        if deleted_paths:
            app.db.mark_files_deleted_by_paths(workspace_id, deleted_paths)
        if errors:
            messagebox.showerror("파일 삭제", "일부 파일 삭제에 실패했습니다:\n\n" + "\n".join(errors), parent=app.root)
        run_search()

    table.bind("<<TreeviewSelect>>", _update_action_buttons)
    table.bind("<Double-1>", lambda _event: open_files())

    search_btn.config(command=run_search)
    clear_btn.config(command=clear_filters_only)
    open_file_btn.config(command=open_files)
    delete_file_btn.config(command=delete_files)

    _update_action_buttons()
