from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    from models.client import Client
    from models.plant import Plant
    from models.consumer_unit import ConsumerUnit, PlantConnection

    CORS(app)

    from routes.config_routes import config_routes
    from routes.drive_routes import drive_routes
    from routes.health_routes import health_routes

    app.register_blueprint(health_routes)
    app.register_blueprint(drive_routes)
    app.register_blueprint(config_routes)

    return app


app = create_app()


if __name__ == '__main__':
    app.run(port=Config.API_PORT, debug=Config.DEBUG)