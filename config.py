from os import getenv


class Config:

    FLASK_DEBUG = getenv('FLASK_DEBUG')
    SECRET_KEY = getenv('SECRET_KEY')

    # jwt configuration
    JWT_SECRET_KEY = getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = int(getenv('JWT_ACCESS_TOKEN_EXPIRES', 900))
    JWT_REFRESH_TOKEN_EXPIRES = int(getenv('JWT_REFRESH_TOKEN_EXPIRES', 1800))

    # database configurations
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = getenv('DATABASE_URL')


