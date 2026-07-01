import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

import applemango_dms.config as config
import applemango_dms.state as state

from applemango_dms.services.auth import clear_saved_credentials
from applemango_dms.services.nas import get_mapped_network_drives
from applemango_dms.utils.windows import apply_window_icon

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
    settings_win = tk.Toplevel(app.root)
    settings_win.title("애플망고 DMS - 설정")
    settings_win.geometry("260x300")
    settings_win.configure(bg="white")
    settings_win.transient(app.root)

    page = tk.Frame(settings_win, bg="white", padx=16, pady=16)
    page.pack(fill="both", expand=True)

    button_column = tk.Frame(page, bg="white")
    button_column.pack(expand=True)

    def settings_btn(label, command):
        tk.Button(
            button_column,
            text=label,
            width=22,
            bg="#d9d9d9",
            activebackground="#c0c0c0",
            relief="flat",
            bd=0,
            cursor="hand2",
            command=command,
        ).pack(pady=4)

    settings_btn("서버 이름 변경", lambda: show_change_server_name_dialog(app, settings_win))
    settings_btn("매핑된 드라이브 관리", lambda: show_mapped_drives_window(settings_win))
    settings_btn(
        "문서 유형 관리",
        lambda: messagebox.showinfo("문서 유형", "문서 유형 관리 기능은 추후 제공됩니다.", parent=settings_win),
    )
    settings_btn(
        "저장된 로그인 정보 삭제",
        lambda: (clear_saved_credentials(), messagebox.showinfo("설정", "저장된 로그인 정보를 삭제했습니다.", parent=settings_win)),
    )
    settings_btn("닫기", settings_win.destroy)
