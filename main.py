from gui_login import LoginWindow
from gui_dashboard import Dashboard

def main():
    def on_login(user):
        app = Dashboard(user)
        app.mainloop()
    login = LoginWindow(on_login)
    login.mainloop()

if __name__ == "__main__":
    main()
