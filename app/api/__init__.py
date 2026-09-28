from app.api.user import users_blp


def register_api(app):
    app.register_blueprint(users_blp)

