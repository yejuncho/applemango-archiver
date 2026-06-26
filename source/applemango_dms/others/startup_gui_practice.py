import tkinter as tk
from tkinter import messagebox, simpledialog
import subprocess

server_path = r"\\applemango"
drive_letter = "Z:"

def map_network_device(root):
    print("applemango_archiver.py")

def run_archiver(root):
    print("applemango_archiver.py")

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
        font = ("Segoe UI", 12, "bold")
    ).pack(pady = (0, 14))
    
    tk.Label(
        container,
        text = " Current Server Path: " + server_path,
        font = ("Segoe UI", 10)
    ).pack(pady = (0, 10))

    tk.Button(
        container,
        text = "Change Server Path",
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
        command = lambda: change_server_path(root)
    ).pack(pady = 6)

    tk.Button(
        container,
        text = "Map Network Drive",
        width = 28,
        height = 2,
        command = lambda: map_network_device(root)
    ).pack(pady = 6)
    
    tk.Button(
        container,
        text = "Run Archiver",
        width = 28,
        height = 2,
        command = lambda: run_archiver(root)
    ).pack(pady = 6)

    root.mainloop()

if __name__ == "__main__":
    main()