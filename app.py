import sys
import logging

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_restful import Api

from config import Config

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))

# db
db = SQLAlchemy()
migrate = Migrate()

# jwt
jwt = JWTManager()
jwt.invalid_token_loader(lambda *_: ({'token': 'Token is invalid'}, 400))
jwt.expired_token_loader(lambda *_: ({'token': 'Token has expired'}, 401))

# cors
cors = CORS()

# api
api = Api()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # init db
    db.init_app(app)
    migrate.init_app(app, db)

    # init jwt
    jwt.init_app(app)

    # init cors
    cors.init_app(app, resources={r'*': {'origins': '*'}})

    # url converters
    from commons.url_converters import DatetimeConverter
    app.url_map.converters['datetime'] = DatetimeConverter

    # blueprints
    from api import api_blueprint
    api.init_app(api_blueprint)
    app.register_blueprint(api_blueprint, url_prefix='/api')

    app.app_context().push()
    db.create_all()

    return app


created_app = create_app()

if __name__ == '__main__':
    created_app.run()
