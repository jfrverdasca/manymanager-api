from flask import Blueprint, current_app
from flask_restful import Resource, reqparse
from flask_jwt_extended import jwt_required, create_access_token, create_refresh_token, get_jwt_identity
from sqlalchemy.sql import or_

import logging

from app import api
from models import db, User
from commons.decorators.reqparser import req_parser

logger = logging.getLogger(__name__)

auth_blueprint = Blueprint('auth', __name__)


class AuthenticationResource(Resource):

    post_args_parser = reqparse.RequestParser(bundle_errors=True)
    post_args_parser.add_argument('username', type=str, required=True, help='Username is required')
    post_args_parser.add_argument('password', type=str, required=True, help='Password is required')

    @req_parser(post_args_parser)
    def post(self, request_args):
        user = User.query.filter(or_(
            User.username == request_args.username,
            User.email == request_args.username)) \
            .first()

        if not user or not user.verify_password(request_args.password):
            return {'error': 'Wrong username or password'}, 401

        # if user account is disabled, login will activate it again
        elif not user.active:
            user.active = True
            db.session.commit()

        return {
            'access_token': create_access_token(identity=user.id),
            'refresh_token': create_refresh_token(identity=user.id),
            'expires': current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES')
        }


api.add_resource(AuthenticationResource, '/auth/token/')


class TokenRefreshResource(Resource):

    @jwt_required(refresh=True)
    def post(self):
        user_id = get_jwt_identity()

        return {
            'access_token': create_access_token(identity=user_id),
            'refresh_token': create_refresh_token(identity=user_id),
            'expires': current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES')
        }


api.add_resource(TokenRefreshResource, '/auth/token/refresh/')
