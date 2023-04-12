from flask import Blueprint
from flask_restful import Resource, marshal, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.sql import func

from datetime import datetime
from calendar import monthrange

from app import api
from models import Expense, Category, User, Share
from api.expense.routes import EXPENSE_FIELDS
from api.category.routes import CATEGORY_FIELDS
from commons.datatable import DatatableHandler, datatable_request_parser


datatables_blueprint = Blueprint('datatables', __name__)


FAVORITES_DATATABLE_FIELDS = {
    'description': fields.String,
    'category': fields.Nested({
        'color': fields.String
    }, attribute='category'),
    'amount': fields.Float,
    'favorite_order': fields.Integer
}

SHARES_DATATABLE_FIELDS = {
    'username': fields.String(attribute='shared_with.username'),
    'id': fields.Nested({
        'shared_by_user_id': fields.Integer,
        'shared_with_user_id': fields.Integer
    }, attribute=lambda obj: obj)  # pass the Share object to the nested field
}


class ExpensesDatatableResource(Resource, DatatableHandler):

    COLUMNS = {
        0: Expense.description,
        1: Category.name,
        2: Expense.timestamp,
        3: Expense.amount,
        4: 'Options',
        5: 'Shared',
        6: Expense.paid
    }

    @jwt_required()
    @datatable_request_parser()
    def get(self, start_date=None, end_date=None, category=0):
        user_id = get_jwt_identity()

        # set start_date and end_date if not set
        datetime_now = datetime.now()
        if not start_date:
            start_date = datetime_now.replace(day=1)

        if not end_date:
            _, last_month_day = monthrange(datetime_now.year, datetime_now.month)
            end_date = datetime_now.replace(day=last_month_day)

        # add hour information to data
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        expenses = Expense.get_user_expenses_date_interval(user_id,
                                                           start_date,
                                                           end_date,
                                                           category)

        paginate = super().handle_request(expenses)

        return {
            'data': marshal(paginate.items, EXPENSE_FIELDS),
            'recordsTotal': paginate.total,
        }


api.add_resource(ExpensesDatatableResource,
                 '/expenses-datatable/',
                 '/expenses-datatable/<datetime:start_date>/<datetime:end_date>/<int:category>/')


class CategoriesDatatableResource(Resource, DatatableHandler):

    COLUMNS = {
        0: Category.name,
        1: Category.limit,
        2: 'Options'
    }

    @jwt_required()
    @datatable_request_parser()
    def get(self):
        user_id = get_jwt_identity()

        paginate = super().handle_request(Category.query.filter_by(user_id=user_id))

        return {
            'data': marshal(paginate.items, CATEGORY_FIELDS),
            'recordsTotal': paginate.total
        }


api.add_resource(CategoriesDatatableResource, '/categories-datatable/')


class CategoriesBalanceDatatableResource(Resource, DatatableHandler):

    COLUMNS = {
        0: Category.name,
        1: 'Limit',
        2: 'Balance',
        3: 'Spent'
    }

    @jwt_required()
    @datatable_request_parser()
    def get(self, start_date=None, end_date=None, category=0):
        user_id = get_jwt_identity()

        # set start_date and end_date if not set
        datetime_now = datetime.now()
        if not start_date:
            start_date = datetime_now.replace(day=1)

        if not end_date:
            _, last_month_day = monthrange(datetime_now.year, datetime_now.month)
            end_date = datetime_now.replace(day=last_month_day)

        # add hour information to data
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)

        # calculate the number of months between start date and end date
        months = ((end_date.year - start_date.year) * 12 + end_date.month - start_date.month) + 1

        expenses = Expense.get_user_expenses_date_interval(user_id,
                                                           start_date,
                                                           end_date,
                                                           category) \
            .with_entities(Category, func.sum(Expense.amount).label('total_amount')) \
            .group_by(Category.id) \
            .order_by(Category.name)

        paginate = super().handle_request(expenses)

        return {
            'recordsTotal': paginate.total,
            'data': [{
                'category': {
                    'name': category.name,
                    'color': category.color
                },
                'limit': (months_limit := round(category.limit * months, 2)),
                'balance': round(months_limit - total_amount, 2),
                'spent': round(total_amount, 2)
            } for category, total_amount in paginate.items]
        }


api.add_resource(CategoriesBalanceDatatableResource,
                 '/categories-balance-datatable',
                 '/categories-balance-datatable/<datetime:start_date>/<datetime:end_date>/<int:category>/')


class FavoritesDatatableResource(Resource, DatatableHandler):

    COLUMNS = {
        0: Expense.description,
        1: Expense.amount,
        2: 'Options',
        3: Expense.favorite_order
    }

    @jwt_required()
    @datatable_request_parser()
    def get(self):
        user_id = get_jwt_identity()

        paginate = super().handle_request(
            Expense.query.filter_by(user_id=user_id, is_favorite=True)
            .join(Category, Expense.category_id == Category.id))

        return {
            'data': marshal(paginate.items, FAVORITES_DATATABLE_FIELDS),
            'recordsTotal': paginate.total
        }


api.add_resource(FavoritesDatatableResource, '/favorites-datatable/')


class SharesDatatableResource(Resource, DatatableHandler):

    COLUMNS = {
        0: User.username,
        1: 'Options'
    }

    @jwt_required()
    @datatable_request_parser()
    def get(self):
        user_id = get_jwt_identity()

        paginate = super().handle_request(
            Share.query.filter_by(shared_by_user_id=user_id)
            .join(User, Share.shared_with_user_id == User.id)
        )

        return {
            'data': marshal(paginate.items, SHARES_DATATABLE_FIELDS),
            'recordsTotal': paginate.total
        }


api.add_resource(SharesDatatableResource, '/shares-datatable/')
