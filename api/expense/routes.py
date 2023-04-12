from flask import Blueprint
from flask_restful import Resource, reqparse, marshal, fields
from flask_jwt_extended import jwt_required, get_jwt_identity

import logging
from types import SimpleNamespace
from datetime import datetime, date, time

from app import api
from models import db, Expense, Category, Share, User
from api.category.routes import CATEGORY_FIELDS
from commons.decorators.reqparser import req_parser


logger = logging.getLogger(__name__)

expense_blueprint = Blueprint('expense', __name__)

SHARES_FIELDS = {
    'user_id': fields.Integer,
    'amount': fields.Float,
    'paid': fields.Boolean
}

EXPENSE_FIELDS = {
    'id': fields.Integer,
    'description': fields.String,
    'category': fields.Nested(CATEGORY_FIELDS),
    'date': fields.String(attribute=lambda obj: obj.timestamp.date()),
    'time': fields.String(attribute=lambda obj: obj.timestamp.time()),
    'timestamp': fields.String(),
    'amount': fields.Float,
    'paid': fields.Boolean,
    'is_favorite': fields.Boolean,
    'favorite_order': fields.Integer,
    'parent_id': fields.Integer,
    'shares': fields.Nested(SHARES_FIELDS, default=True, attribute='children'),
    'is_owner': fields.Boolean
}


class ExpenseResource(Resource):

    @staticmethod
    def _validate_date(value):
        if value:
            try:
                return date.fromisoformat(value)

            except ValueError:
                raise ValueError('Invalid date format')

    @staticmethod
    def _validate_time(value):
        if value:
            try:
                return time.fromisoformat(value)

            except ValueError:
                raise ValueError('Invalid time format')

    @staticmethod
    def _validate_amount(value):
        if value:
            try:
                value = float(value)

            except ValueError:
                raise ValueError('Invalid amount value')

            if value < 0:
                raise ValueError('Amount cannot be lower than 0')

            return value

    post_args_parse = reqparse.RequestParser(bundle_errors=True)
    post_args_parse.add_argument('description', type=str, required=True, help='Description is required')
    post_args_parse.add_argument('category', type=int, required=True, help='Category is required')
    post_args_parse.add_argument('date', type=_validate_date, required=True, help='Date is required')
    post_args_parse.add_argument('time', type=_validate_time, required=True, help='Time is required')
    post_args_parse.add_argument('amount', type=_validate_amount, required=True, help='Amount is required')
    post_args_parse.add_argument('paid', type=bool, default=True)
    post_args_parse.add_argument('is_favorite', type=bool, default=False)
    post_args_parse.add_argument('favorite_order', type=int)
    post_args_parse.add_argument('shares', type=dict, default=[], action='append')

    shares_args_parse = reqparse.RequestParser(bundle_errors=True)
    shares_args_parse.add_argument('user_id', type=int, location='json', required=True,
                                   help='Share user id is required')
    shares_args_parse.add_argument('amount', type=float, location='json', required=True,
                                   help='Share amount is required')
    shares_args_parse.add_argument('paid', type=bool, location='json', default=False)

    @jwt_required()
    def get(self, expense_id=None):
        user_id = get_jwt_identity()

        if expense_id and (expense := Expense.query.filter_by(id=expense_id, user_id=user_id).first()):
            return marshal(expense, EXPENSE_FIELDS)

        elif not expense_id:
            return marshal(Expense.query.filter_by(user_id=user_id).all(), EXPENSE_FIELDS)

        else:
            return {'error': 'Expense does not exist or does not belong to user'}, 404

    @jwt_required()
    @req_parser(post_args_parse)
    def post(self, parsed_args, expense_id=None):
        user_id = get_jwt_identity()

        # merge date and time as timestamp and remove date and time properties for
        # direct expense creation from parsed_args object
        # note: replace(microsecond=0) remove microsecond info from datetime object
        parsed_args.timestamp = datetime.combine(parsed_args.date, parsed_args.time).replace(microsecond=0)
        del parsed_args['date'], parsed_args['time']

        # shares validation (using args_parse)
        shares = \
            list(map(lambda v: self.shares_args_parse.parse_args(SimpleNamespace(**{'json': v})),
                     parsed_args.pop('shares')))

        # shares permission check
        unallowed_shares_user_ids = {s.user_id for s in shares} \
            .difference(
                {s.shared_with_user_id for s in Share.query
                    .join(User, Share.shared_with_user_id == User.id)
                    .with_entities(Share.shared_with_user_id)
                    .filter(Share.shared_by_user_id == user_id,
                            User.active).all()})
        if unallowed_shares_user_ids:
            # convert unallowed_shares_user_ids from set to string to user in messages bellow
            unallowed_shares_user_ids = ', '.join(map(lambda v: str(v), unallowed_shares_user_ids))

            logger.error(f'Attempt to share an expense with a user without permission or non-existent: '
                         f'{unallowed_shares_user_ids}')
            return {'message':
                    {'shares': f'User is not allowed to share expenses with user(s): {unallowed_shares_user_ids}'}}, 400

        # check if the expense category exists and belong to user
        if category := Category.query.filter_by(id=parsed_args.category, active=True, user_id=user_id).first():
            parsed_args.category = category

        else:
            return {'message':
                    {'category': 'Category is disabled, does not exist or does not belong to user'}}, 400

        response_code = None
        if expense_id and (expense := Expense.query.filter_by(id=expense_id, user_id=user_id).first()):
            # validate shared expense amount if not owner
            if expense.parent_id and parsed_args.amount and parsed_args.amount != expense.amount:
                return {'message':
                        {'amount': 'Cannot change the amount of a shared expense'}}

            list(map(lambda arg: setattr(expense, arg, parsed_args[arg]), parsed_args))

        else:
            response_code = 201

            expense = Expense(**parsed_args, user_id=user_id)
            db.session.add(expense)

        db.session.commit()

        # handle expense shares
        has_uncommitted_changes = False
        for share in shares:
            shared_expense = Expense.query.filter_by(user_id=share.user_id, parent_id=expense.id).first()
            # added shared expense
            if not shared_expense:
                try:
                    shared_expense = expense.create_shared_expense(share.user_id, share.amount, share.paid)
                    db.session.add(shared_expense)

                except PermissionError as permission_error:
                    logger.warning(f'Expense {expense.id} not shared with user {share.user_id}:',
                                   exc_info=permission_error)

            # removed shared expense
            elif share.amount in [None, 0]:
                db.session.delete(shared_expense)

            # updated shared expense
            elif share.amount != shared_expense.amount or share.paid != shared_expense.paid:
                shared_expense.amount = share.amount
                shared_expense.paid = share.paid

            else:
                continue  # avoid changing the value of the flag bellow

            has_uncommitted_changes = True

        if has_uncommitted_changes:
            db.session.commit()

        return marshal(expense, EXPENSE_FIELDS), response_code

    @jwt_required()
    def delete(self, category_id):
        user_id = get_jwt_identity()

        if expense := Expense.query.filter_by(id=category_id, user_id=user_id).first():
            db.session.delete(expense)
            db.session.commit()

            return marshal(expense, EXPENSE_FIELDS)

        else:
            return {'error': 'Expense does not exist or does not belong to user'}, 404


api.add_resource(ExpenseResource, '/expense/', '/expense/<int:expense_id>/')
