from flask import Flask
from flask_cors import CORS

from config import Config
from routes.config_routes import config_routes
from routes.drive_routes import drive_routes
from routes.health_routes import health_routes


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app)
    app.register_blueprint(health_routes)
    app.register_blueprint(drive_routes)
    app.register_blueprint(config_routes)

    return app


app = create_app()


if __name__ == '__main__':
    app.run(port=Config.API_PORT, debug=Config.DEBUG)
