def show_login_screen(app, prefill_username=None):
    return app.show_login_screen(prefill_username=prefill_username)


def show_username_login_screen(app):
    return app.show_username_login_screen()


def show_password_login_screen(app, username):
    return app.show_password_login_screen(username)
