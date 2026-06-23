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

    tk.Label(win, text="매핑된 네트워크 드라이브", font=("Segoe UI", 10, "bold"), bg="white").pack(pady=(10, 8))

    frame = tk.Frame(win, bg="white")
    frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    listbox = tk.Listbox(frame, font=("Segoe UI", 10), activestyle="none", selectmode="extended")
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
