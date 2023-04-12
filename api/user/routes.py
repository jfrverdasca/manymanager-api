from flask import Blueprint
from flask_restful import Resource, reqparse, marshal, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError

import logging

from app import api
from models import db, User
from commons.decorators.reqparser import req_parser


logger = logging.getLogger(__name__)

user_blueprint = Blueprint('user', __name__)

USER_FIELDS = {
    'id': fields.Integer,
    'email': fields.String,
    'username': fields.String,
    'active': fields.Boolean,
    'created_timestamp': fields.DateTime(dt_format='iso8601'),
    'updated_timestamp': fields.DateTime(dt_format='iso8601')
}


class UserResource(Resource):

    post_args_parse = reqparse.RequestParser(bundle_errors=True)
    post_args_parse.add_argument('email', type=str, required=True, help='Email is required')
    post_args_parse.add_argument('username', type=str, required=True, help='Username is required')
    post_args_parse.add_argument('password', type=str, required=True, help='Password is required')
    post_args_parse.add_argument('active', type=bool)

    patch_args_parse = reqparse.RequestParser(bundle_errors=True)
    patch_args_parse.add_argument('email', type=str)
    patch_args_parse.add_argument('username', type=str)
    patch_args_parse.add_argument('password', type=str)
    patch_args_parse.add_argument('active', type=bool)

    @jwt_required()
    def get(self, user_id=None):
        user_id = user_id or get_jwt_identity()

        if user := User.query.filter_by(id=user_id, active=True).first():
            return marshal(user, USER_FIELDS)

        return {'error': 'User is disabled or does not exist'}, 404

    @jwt_required(optional=True)  # no jwt is user create, jwt is present is user update
    @req_parser(post_args_parse)
    def post(self, parsed_args, user_id=None):  # user id avoid error and 500 response
        if user_id:
            return {'error': 'It is not possible to change data of other users'}, 401

        return self._post_patch_handler(parsed_args, get_jwt_identity())

    @jwt_required()
    @req_parser(patch_args_parse)
    def patch(self, parsed_args, user_id=None):  # user id avoid error and 500 response
        if user_id:
            return {'error': 'It is not possible to change data of other users'}, 401

        return self._post_patch_handler(parsed_args, get_jwt_identity())

    @jwt_required()
    def delete(self, user_id=None):
        if user_id:
            return {'error': 'It is not possible to change data of other users'}, 401

        user_id = get_jwt_identity()

        if user := User.query.filter_by(id=user_id).first():
            user.active = False
            db.session.commit()

            return marshal(user, USER_FIELDS)

        else:
            return {'error': 'User is disabled or does not exist'}, 404

    @staticmethod
    def _post_patch_handler(parsed_args, user_id):
        response_code = None
        if user_id and (user := User.query.filter_by(id=user_id).first()):
            # set user object property if property has a value
            list(map(lambda arg: setattr(user, arg, parsed_args[arg]) if parsed_args[arg] else True, parsed_args))

        elif not user_id:
            response_code = 201

            user = User(**parsed_args)
            db.session.add(user)

        else:
            return {'error': 'The user does not exist'}, 404

        try:
            db.session.commit()

        except IntegrityError as integrity_error:
            logger.error('Attempt to create user with existing email or username:', exc_info=integrity_error)
            return {'error': 'Email or username already exists'}

        return marshal(user, USER_FIELDS), response_code


api.add_resource(UserResource, '/user/', '/user/<int:user_id>/')
