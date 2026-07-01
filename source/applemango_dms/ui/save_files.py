import shutil
import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import applemango_dms.state as state

try:
    import importlib

    _tkinterdnd2 = importlib.import_module("tkinterdnd2")
    DND_FILES = _tkinterdnd2.DND_FILES
    TkinterDnD = _tkinterdnd2.TkinterDnD
except ImportError:
    DND_FILES = None
    TkinterDnD = None


def show_save_files_screen(app):
    shell = app._create_workspace_shell()
    app.root.title("애플망고 DMS - 파일 저장")

    app._build_sidebar_nav(
        shell["sidebar"],
        "save",
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
    app._build_workspace_page_header(outer, "파일 저장", "파일을 드래그 앤 드롭하거나, 아래 버튼을 클릭하여 파일을 선택하세요.")

    board = tk.Frame(outer, bg="#ffffff", highlightthickness=1, highlightbackground="#e3e9f7", padx=14, pady=14)
    board.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    selected_files = []
    date_var = tk.StringVar(value=date.today().isoformat())
    uploaded_by_var = tk.StringVar(value=state.session_account_name or state.session_username)
    tags_var = tk.StringVar(value="")
    doc_types = app.db.get_document_types()
    doc_type_var = tk.StringVar(value=("기타" if "기타" in doc_types else doc_types[0]))
    app._bind_iso_date_formatter(date_var)

    controls = tk.Frame(board, bg="#ffffff")
    controls.pack(fill="x", pady=(0, 10))
    tk.Label(controls, text="날짜", font=app._font(9, "bold"), bg="#ffffff", fg="#4b556c").pack(side="left")
    tk.Entry(controls, textvariable=date_var, width=12).pack(side="left", padx=(6, 10))
    tk.Label(controls, text="문서 유형", font=app._font(9, "bold"), bg="#ffffff", fg="#4b556c").pack(side="left")
    ttk.Combobox(controls, textvariable=doc_type_var, values=doc_types, state="readonly", width=14).pack(side="left", padx=(6, 10))
    tk.Label(controls, text="태그", font=app._font(9, "bold"), bg="#ffffff", fg="#4b556c").pack(side="left")
    tk.Entry(controls, textvariable=tags_var, width=24).pack(side="left", padx=(6, 10))

    status_text = tk.StringVar(value="업로드 대기 파일 0개")
    tk.Label(controls, textvariable=status_text, font=app._font(9), bg="#ffffff", fg="#7a8398").pack(side="right")

    drop_wrap = tk.Frame(board, bg="#f8faff", highlightthickness=0, bd=0)
    drop_wrap.pack(fill="x", pady=(0, 12))
    drop_area = tk.Canvas(drop_wrap, height=170, bg="#f8faff", highlightthickness=0, bd=0, cursor="hand2")
    drop_area.pack(fill="x", padx=8, pady=8)

    select_btn = tk.Button(
        drop_wrap,
        text="파일 선택",
        bg="#edf0f6",
        fg="#3f495f",
        activebackground="#dde2ee",
        activeforeground="#3f495f",
        relief="flat",
        bd=0,
        cursor="hand2",
        padx=16,
        pady=5,
    )
    drop_area.create_window(0, 0, window=select_btn, anchor="center", tags="select_btn")

    pending_box = tk.Frame(board, bg="#ffffff", highlightthickness=1, highlightbackground="#e5ebf8", padx=8, pady=8)
    pending_box.pack(fill="x", pady=(0, 12))
    tk.Label(pending_box, text="업로드 대기 파일", bg="#ffffff", fg="#24345a", font=app._font(10, "bold"), anchor="w").pack(fill="x", pady=(0, 6))

    pending_tree = ttk.Treeview(pending_box, columns=("name", "preview"), show="headings", height=4)
    pending_tree.heading("name", text="원본 파일명")
    pending_tree.heading("preview", text="저장 파일명 미리보기")
    pending_tree.column("name", width=320, anchor="w")
    pending_tree.column("preview", width=460, anchor="w")
    pending_tree.pack(side="left", fill="x", expand=True)
    pending_scroll = ttk.Scrollbar(pending_box, orient="vertical", command=pending_tree.yview)
    pending_scroll.pack(side="right", fill="y")
    pending_tree.configure(yscrollcommand=pending_scroll.set)

    btn_row = tk.Frame(board, bg="#ffffff")
    btn_row.pack(fill="x", pady=(0, 12))
    tk.Button(
        btn_row,
        text="선택 항목 제거",
        width=14,
        bg="#eef2fa",
        fg="#334264",
        activebackground="#dde6f7",
        relief="flat",
        bd=0,
        cursor="hand2",
        command=lambda: remove_selected_rows(),
    ).pack(side="left")
    tk.Button(
        btn_row,
        text="파일 저장",
        width=14,
        bg="#4a556f",
        fg="white",
        activebackground="#3f485f",
        relief="flat",
        bd=0,
        cursor="hand2",
        command=lambda: save_files(),
    ).pack(side="left", padx=(8, 0))

    recent_wrap = tk.Frame(board, bg="#ffffff", highlightthickness=1, highlightbackground="#e5ebf8", padx=8, pady=8)
    recent_wrap.pack(fill="both", expand=True)
    tk.Label(recent_wrap, text="최근 업로드 파일", bg="#ffffff", fg="#24345a", font=app._font(10, "bold"), anchor="w").pack(fill="x", pady=(0, 6))

    recent_tree = ttk.Treeview(recent_wrap, columns=("file", "size", "updated", "menu"), show="headings", height=8)
    recent_tree.heading("file", text="파일명")
    recent_tree.heading("size", text="크기")
    recent_tree.heading("updated", text="수정일")
    recent_tree.heading("menu", text="")
    recent_tree.column("file", width=530, anchor="w")
    recent_tree.column("size", width=110, anchor="e")
    recent_tree.column("updated", width=170, anchor="w")
    recent_tree.column("menu", width=40, anchor="center")
    recent_tree.pack(side="left", fill="both", expand=True)
    recent_scroll = ttk.Scrollbar(recent_wrap, orient="vertical", command=recent_tree.yview)
    recent_scroll.pack(side="right", fill="y")
    recent_tree.configure(yscrollcommand=recent_scroll.set)

    style = ttk.Style()
    style.configure("Workspace.Treeview", rowheight=28)
    pending_tree.configure(style="Workspace.Treeview")
    recent_tree.configure(style="Workspace.Treeview")

    activity_frame = tk.Frame(board, bg="#ffffff")
    activity_frame.pack(fill="x", pady=(10, 0))
    tk.Label(activity_frame, text="작업 로그", bg="#ffffff", fg="#24345a", font=app._font(10, "bold"), anchor="w").pack(fill="x")
    activity_text = tk.Text(activity_frame, height=5, wrap="word", state="disabled", bg="#fbfcff")
    activity_text.pack(fill="x", pady=(4, 0))

    def append_log(text):
        stamp = datetime.now().strftime("%H:%M:%S")
        activity_text.config(state="normal")
        activity_text.insert("end", f"[{stamp}] {text}\n")
        activity_text.see("end")
        activity_text.config(state="disabled")

    def build_preview_map():
        previews = {}
        destination = app.get_workspace_root_path()
        reserved = set()
        for path in selected_files:
            candidate = app.filename_builder.build_filename(
                date_var.get().strip(), doc_type_var.get(), tags_var.get(), Path(path).name)
            previews[path] = app.filename_builder.ensure_unique_name(
                destination, candidate, reserved) if destination else candidate
        return previews

    def refresh_file_table(*_):
        previews = build_preview_map()
        pending_tree.delete(*pending_tree.get_children())
        for idx, item in enumerate(selected_files):
            src = Path(item)
            pending_tree.insert("", "end", iid=f"f{idx}", values=(src.name, previews.get(item, src.name)))
        status_text.set(f"업로드 대기 파일 {len(selected_files)}개")

    def add_file_paths(paths):
        normalized = []
        for raw in paths:
            candidate = str(raw).strip().strip("{}")
            if candidate and Path(candidate).is_file():
                normalized.append(str(Path(candidate)))
        if not normalized:
            return
        seen = set(selected_files)
        for item in normalized:
            if item not in seen:
                selected_files.append(item)
                seen.add(item)
        refresh_file_table()

    def add_folder_paths(folder_paths):
        discovered = []
        for raw in folder_paths:
            folder_candidate = str(raw).strip().strip("{}")
            folder = Path(folder_candidate)
            if folder_candidate and folder.is_dir():
                discovered.extend(str(p) for p in folder.rglob("*") if p.is_file())
        add_file_paths(discovered)

    def remove_selected_rows():
        selected = pending_tree.selection()
        if not selected:
            return
        names = {pending_tree.item(iid, "values")[0] for iid in selected}
        selected_files[:] = [item for item in selected_files if Path(item).name not in names]
        refresh_file_table()

    def pick_files():
        files = filedialog.askopenfilenames(parent=app.root, title="파일 추가")
        if files:
            add_file_paths(files)

    def handle_drop(event):
        dropped = app.root.tk.splitlist(event.data)
        file_items, folder_items = [], []
        for item in dropped:
            normalized = str(item).strip().strip("{}")
            if not normalized:
                continue
            path_obj = Path(normalized)
            if path_obj.is_file():
                file_items.append(normalized)
            elif path_obj.is_dir():
                folder_items.append(normalized)
        if file_items:
            add_file_paths(file_items)
        if folder_items:
            add_folder_paths(folder_items)
        return event.action if hasattr(event, "action") else None

    def save_files():
        if not selected_files:
            messagebox.showerror("파일 저장", "저장할 파일을 1개 이상 추가하세요.", parent=app.root)
            return
        try:
            archive_date = datetime.strptime(date_var.get().strip(), "%Y-%m-%d").date().isoformat()
        except ValueError:
            messagebox.showerror("파일 저장", "날짜 형식은 YYYY-MM-DD 이어야 합니다.", parent=app.root)
            return
        if not state.active_workspace:
            messagebox.showerror("파일 저장", "활성 워크스페이스가 없습니다.", parent=app.root)
            return
        destination = app.get_workspace_root_path()
        if state.is_demo_mode and destination:
            destination.mkdir(parents=True, exist_ok=True)
        if not destination or not destination.exists() or not destination.is_dir():
            messagebox.showerror("파일 저장", "워크스페이스 저장 경로를 사용할 수 없습니다.", parent=app.root)
            return
        for source in selected_files:
            if not Path(source).is_file():
                messagebox.showerror("파일 저장", f"파일을 찾을 수 없습니다:\n{source}", parent=app.root)
                return

        previews = build_preview_map()
        saved_count = 0
        failures = []

        for source in selected_files:
            src = Path(source)
            archived_name = previews.get(source, src.name)
            dst = destination / archived_name
            try:
                shutil.copy2(src, dst)
                size = dst.stat().st_size if dst.exists() else 0
                app.db.insert_file_record({
                    "workspace": state.active_workspace,
                    "original_filename": src.name,
                    "archived_filename": archived_name,
                    "full_path": str(dst),
                    "document_type": doc_type_var.get(),
                    "tags": tags_var.get().strip(),
                    "uploaded_by": uploaded_by_var.get(),
                    "archive_date": archive_date,
                    "archived_at": datetime.now().isoformat(timespec="seconds"),
                    "file_ext": src.suffix,
                    "file_size": size,
                    "source_path": str(src),
                })
                saved_count += 1
                append_log(f"저장 완료: {archived_name}")
            except Exception as exc:
                failures.append(f"{src.name}: {exc}")
                append_log(f"저장 실패: {src.name} ({exc})")

        if saved_count and not failures:
            messagebox.showinfo("파일 저장", f"{saved_count}개 파일을 저장했습니다.", parent=app.root)
        elif saved_count and failures:
            messagebox.showwarning("파일 저장",
                f"{saved_count}개 저장 완료.\n{len(failures)}개 저장 실패.\n\n" + "\n".join(failures[:8]),
                parent=app.root)
        else:
            messagebox.showerror("파일 저장", "저장된 파일이 없습니다.\n\n" + "\n".join(failures[:8]),
                                 parent=app.root)
        load_recent_files()
        refresh_file_table()

    def load_recent_files():
        recent_tree.delete(*recent_tree.get_children())
        if not state.active_workspace:
            return
        rows = app._get_recent_workspace_files(state.active_workspace, limit=8)
        for idx, row in enumerate(rows):
            archive_date, _document_type, _tags, archived_filename, _uploaded_by, file_size, _full_path = row
            icon_text, _icon_color = app._file_type_icon(archived_filename)
            size_text = app._format_size_for_display(int(file_size or 0))
            updated_text = archive_date.replace("-", "/") if isinstance(archive_date, str) else "-"
            recent_tree.insert("", "end", iid=f"recent-{idx}", values=(f"{icon_text}  {archived_filename}", size_text, updated_text, "\u22ee"))

    def redraw_drop_area(_event=None):
        drop_area.delete("all")
        width = max(360, drop_area.winfo_width())
        height = max(150, drop_area.winfo_height())
        app._smooth_rounded_rect(
            drop_area,
            6,
            6,
            width - 6,
            height - 6,
            20,
            fill="#f8faff",
            outline="#2d6cdf",
            width=2,
            dash=(4, 4),
            tags="drop_outline",
        )
        center_x = width // 2
        cloud_icon = app.ui_icon_photos.get("workspace_cloud_save")
        if cloud_icon is not None:
            drop_area.create_image(center_x, 75, image=cloud_icon, anchor="center", tags="drop_outline")
        else:
            drop_area.create_text(center_x, 75, text="\U0001F4E4", fill="#5c667f", font=("Segoe UI Emoji", 28))
        drop_area.create_text(center_x, 125, text="박스를 클릭하여 파일을 선택하세요", fill="#2f3749", font=app._font(12, "bold"))
        drop_area.coords("select_btn", center_x, 132)

    select_btn.configure(command=pick_files)
    drop_area.bind("<Button-1>", lambda _event: pick_files())
    drop_area.bind("<Configure>", redraw_drop_area)
    if TkinterDnD is not None and hasattr(drop_area, "drop_target_register"):
        drop_area.drop_target_register(DND_FILES)
        drop_area.dnd_bind("<<Drop>>", handle_drop)

    date_var.trace_add("write", refresh_file_table)
    doc_type_var.trace_add("write", refresh_file_table)
    tags_var.trace_add("write", refresh_file_table)
    redraw_drop_area()
    load_recent_files()
    refresh_file_table()
