from flask import Blueprint
from flask_restful import Resource, reqparse, marshal, fields
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import api
from models import db, Category
from commons.decorators.reqparser import req_parser


category_blueprint = Blueprint('category', __name__)

CATEGORY_FIELDS = {
    'id': fields.Integer,
    'name': fields.String,
    'limit': fields.Float,
    'color': fields.String,
    'text_color': fields.String,
    'active': fields.Boolean
}


class CategoryResource(Resource):

    get_args_parse = reqparse.RequestParser()
    get_args_parse.add_argument('only_actives', type=int, default=1, location='args',
                                help='Invalid value: 0 for false or other numeric value for true')

    post_args_parse = reqparse.RequestParser(bundle_errors=True)
    post_args_parse.add_argument('name', type=str, required=True, help='Name is required')
    post_args_parse.add_argument('color', type=str, required=True, help='Color is required')
    post_args_parse.add_argument('limit', type=float, default=0)
    post_args_parse.add_argument('active', type=bool, default=True)

    @jwt_required()
    @req_parser(get_args_parse, strict=False)
    def get(self, parsed_args, category_id=None):
        user_id = get_jwt_identity()

        if category_id and (category := Category.query.filter_by(id=category_id, user_id=user_id).first()):
            return marshal(category, CATEGORY_FIELDS)

        elif not category_id:
            if parsed_args.only_actives:
                return marshal(Category.query.filter_by(user_id=user_id, active=True).all(), CATEGORY_FIELDS)

            return marshal(Category.query.filter_by(user_id=user_id).all(), CATEGORY_FIELDS)

        else:
            return {'error': 'Category is disabled, does not exist or does not belong to user'}, 404

    @jwt_required()
    @req_parser(post_args_parse)
    def post(self, parsed_args, category_id=None):
        user_id = get_jwt_identity()

        # args validation:
        if parsed_args.limit < 0:
            return {'message': {
                'limit': 'Limit cannot be lower than 0'
            }}, 400

        elif len(parsed_args.color) > 7:
            return {'message': {
                'color': 'Color must be in hexadecimal format'
            }}, 400

        elif not parsed_args.color.startswith('#'):
            parsed_args.color = f'#{parsed_args.color}'

        response_code = None
        if category_id and (category := Category.query.filter_by(id=category_id, user_id=user_id).first()):
            list(map(lambda arg: setattr(category, arg, parsed_args[arg]), parsed_args))

        else:
            response_code = 201

            category = Category(**parsed_args, user_id=user_id)
            db.session.add(category)

        db.session.commit()

        return marshal(category, CATEGORY_FIELDS), response_code

    @jwt_required()
    def delete(self, category_id):
        user_id = get_jwt_identity()

        if category := Category.query.filter_by(id=category_id, user_id=user_id).first():
            category.active = False
            db.session.commit()

            return marshal(category, CATEGORY_FIELDS)

        else:
            return {'error': 'Category is disabled, does not exist or does not belong to user'}, 404


api.add_resource(CategoryResource, '/category/', '/category/<int:category_id>/')
