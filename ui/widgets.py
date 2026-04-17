import tkinter as tk


def create_button(parent, text, command, color):
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=("Segoe UI", 10, "bold"),
        bg=color,
        fg="white",
        activeforeground="white",
        relief="flat",
        bd=0,
        padx=12,
        pady=9,
        cursor="hand2",
    )


def create_tool_button(parent, text, command):
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=("Segoe UI", 9, "bold"),
        relief="flat",
        bd=0,
        padx=10,
        pady=7,
        cursor="hand2",
    )
