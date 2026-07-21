from flask import Flask
from flask_cors import CORS

from config import Config
from extensions import db, migrate


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)

    from models.client import Client
    from models.plant import Plant
    from models.consumer_unit import ConsumerUnit, PlantConnection
    from models.category import Category
    from models.document import Document
    from models.setting import Setting
    from models.google_account import GoogleAccount
    from models.log_entry import LogEntry

    CORS(app)

    from routes.config_routes import config_routes
    from routes.drive_routes import drive_routes
    from routes.health_routes import health_routes
    from routes.client_routes import client_routes
    from routes.plant_routes import plant_routes
    from routes.uc_routes import uc_routes

    app.register_blueprint(health_routes)
    app.register_blueprint(drive_routes)
    app.register_blueprint(config_routes)
    app.register_blueprint(client_routes)
    app.register_blueprint(plant_routes)
    app.register_blueprint(uc_routes)

    return app


app = create_app()


if __name__ == '__main__':
    app.run(port=Config.API_PORT, debug=Config.DEBUG)