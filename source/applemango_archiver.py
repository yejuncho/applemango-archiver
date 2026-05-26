import tkinter as tk
from tkinter import ttk
from tkinter import messagebox, simpledialog
import subprocess
from pathlib import Path

def get_server_path():
    return fr"{server_name}\{shared_folder}"

server_name = r"\\applemango"
shared_folder = "test"
server_path = fr"{server_name}\{shared_folder}"
drive_letter = "Z:"

def map_network_drive(root):
    server_path = get_server_path()

    messagebox.showinfo(
        "Map Network Drive",
        f"Server Name: {server_name}\nShared Folder: {shared_folder}"
    )

    username = simpledialog.askstring("Map Network Drive", "Username:", parent = root)
    if not username:
        return
    
    password = simpledialog.askstring(
        "Map Network Drive",
        "Password:",
        parent = root,
        show = "*"
    )
    if password is None:
        return

    cmd = [
        "net", "use",
        drive_letter,
        server_path,
        password,
        f"/user:{username}",
        "/persistent:yes"
    ]

    result = subprocess.run(cmd, capture_output = True, text = True)

    if result.returncode == 0:
        messagebox.showinfo(
            "Success",
            f"Mapped {server_path} to {drive_letter}"
        )

    else:
        messagebox.showerror(
            "Mapping Failed",
            result.stderr.strip() or "Unknown error"
        )

def unmap_network_drive(root):
    cmd = ["net", "use", drive_letter, "/delete", "/y"]

    result = subprocess.run(cmd, capture_output = True, text = True)

    if result.returncode == 0:
        messagebox.showinfo(
            "Success",
            f"Unmapped {drive_letter}"
        )
    else:
        messagebox.showerror(
            "Unmapping Failed",
            result.stderr.strip() or "Unknown error"
        )

def run_archiver(root):
    # archiver logic, automatic process once running. start by scanning the inbox folder

    warning_message = "Archiving will move files from the inbox to the archive folder. Do you want to proceed?"
    if messagebox.askyesno("Confirm Archiving", warning_message):
        # proceed with archiving
        pass
    
    messagebox.showinfo(
        "Testing the script",
        "The program will print the number of files in this directory"
    )

    mapped_drive_path = Path(f"{drive_letter}\\")

    if not mapped_drive_path.exists() or not mapped_drive_path.is_dir():
        messagebox.showerror(
            "Drive Not Found",
            f"{drive_letter} is not accessible. Please map the network drive first."
        )
        return

    subprocess.Popen(["explorer", str(mapped_drive_path)])

    file_count = sum(1 for p in mapped_drive_path.rglob("*") if p.is_file())

    print(f"Total files in {mapped_drive_path}: {file_count}")
    messagebox.showinfo(
        "Archiving Result",
        f"Total files in {mapped_drive_path}: {file_count}"
    )

def admin(root, on_path_changed):
    admin_window = tk.Toplevel(root)
    admin_window.title("Admin Settings")
    admin_window.geometry("300x180")
    admin_window.configure(bg="white")
    admin_window.resizable(False, False)
    admin_window.transient(root)
    admin_window.grab_set()

    def change_server_name():
        global server_name, server_path
        new_name = simpledialog.askstring(
            "Change Server Name",
            "Enter new server name:",
            parent=admin_window,
            initialvalue=server_name
        )
        if new_name:
            server_name = new_name.strip()
            on_path_changed()
            messagebox.showinfo(
                "Server Name Updated",
                f"New server name set to:\n{server_name}",
                parent=admin_window
            )

    def change_shared_folder():
        global shared_folder, server_path
        new_folder = simpledialog.askstring(
            "Change Shared Folder",
            "Enter new shared folder name:",
            parent=admin_window,
            initialvalue=shared_folder
        )
        if new_folder:
            shared_folder = new_folder.strip().strip("\\/")
            on_path_changed()
            messagebox.showinfo(
                "Shared Folder Updated",
                f"New shared folder set to:\n{shared_folder}",
                parent=admin_window
            )

    tk.Label(
        admin_window,
        text="Admin Options",
        bg="white",
        font=("Segoe UI", 11, "bold")
    ).pack(pady=(15, 10))

    tk.Button(
        admin_window,
        text="Change Server Name",
        width=24,
        command=change_server_name
    ).pack(pady=6)

    tk.Button(
        admin_window,
        text="Change Shared Folder",
        width=24,
        command=change_shared_folder
    ).pack(pady=6)

def main():
    root = tk.Tk()
    root.title("Applemango Archiver")
    root.geometry("360x360")
    root.configure(bg = "white")
    root.resizable(False, False)

    container = tk.Frame(root, padx = 20, pady = 20, bg = "white")
    container.pack(expand = True, fill = "both")

    tk.Label(
        container,
        text  = "APPLEMANGO ARCHIVER",
        font = ("Segoe UI", 12, "bold"),
        bg = "white"
    ).pack(pady = (0, 14))
    
    path_var = tk.StringVar()

    def refresh_path_label():
        path_var.set(" Current Server Path: " + get_server_path())

    refresh_path_label()

    tk.Label(
        container,
        textvariable = path_var,
        font = ("Segoe UI", 10),
        bg = "white"
    ).pack(pady = (0, 10))

    tk.Button(
        container,
        text = "Map Network Drive",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: map_network_drive(root)
    ).pack(pady = 6)
    
    tk.Button(
        container,
        text = "Unmap Network Drive",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: unmap_network_drive(root)
    ).pack(pady = 6)

    tk.Button(
        container,
        text = "Run Archiver",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: run_archiver(root)
    ).pack(pady = 6)

    tk.Button(
        container,
        text = "Settings",
        width = 28,
        height = 2,
        bg = "#d9d9d9",
        activebackground = "#c0c0c0",
        fg = "black",
        activeforeground = "black",
        relief = "flat",
        bd = 0,
        highlightthickness = 0,
        cursor = "hand2",
        command = lambda: admin(root, refresh_path_label)
    ).pack(pady = 6)

    root.mainloop()

if __name__ == "__main__":
    main()