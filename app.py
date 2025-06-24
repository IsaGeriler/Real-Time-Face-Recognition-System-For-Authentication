from flask import Flask

import config
from presentation.controllers import video_controller
from database import database
from presentation.controllers import admin, auth, guard, manager


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    database.init_db()
    auth.init_auth_routes(app)
    guard.init_guard_routes(app)
    manager.init_manager_routes(app)
    admin.init_admin_routes(app)
    video_controller.init_video_routes(app)

    return app


if __name__ == '__main__':
    create_app().run(debug=True)
