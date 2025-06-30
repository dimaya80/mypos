import customtkinter as ctk
from tkinter import messagebox
from db import login_user

class LoginWindow(ctk.CTk):
    def __init__(self, on_login):
        super().__init__()
        self.title("MyPOS Login")
        self.geometry("400x300")
        self.on_login = on_login
        self.build_ui()

    def build_ui(self):
        ctk.CTkLabel(self, text="Username:").pack(pady=5)
        self.ent_user = ctk.CTkEntry(self)
        self.ent_user.pack(pady=5)
        ctk.CTkLabel(self, text="Password:").pack(pady=5)
        self.ent_pass = ctk.CTkEntry(self, show="*")
        self.ent_pass.pack(pady=5)
        ctk.CTkButton(self, text="Login", command=self.try_login).pack(pady=10)

    def try_login(self):
        user = login_user(self.ent_user.get(), self.ent_pass.get())
        if user:
            self.destroy()
            self.on_login(user)
        else:
            messagebox.showerror("Login Failed", "Username/password salah")
