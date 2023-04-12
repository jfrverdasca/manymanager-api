from flask import Blueprint
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.sql import func, desc

from math import copysign
from datetime import datetime
from calendar import monthrange, month_name

from app import api
from models import Expense, Category


charts_blueprint = Blueprint('charts', __name__)


class QuickHistoryChartResource(Resource):

    @jwt_required()
    def get(self, months=12):
        user_id = get_jwt_identity()

        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = self._calculate_start_date(end_date, months)

        month_trunc = func.date_trunc('month', Expense.timestamp)
        expenses = Expense.query.filter(Expense.user_id == user_id,
                                        Expense.timestamp >= start_date,
                                        Expense.timestamp <= end_date) \
            .join(Category, Expense.category_id == Category.id) \
            .with_entities(Category, month_trunc, func.sum(Expense.amount).label('total_amount')) \
            .group_by(month_trunc, Category) \
            .order_by(Category.name)

        datasets = dict()
        for category, month, amount in expenses:
            if category.name not in datasets:
                datasets[category.name] = {
                    'label': category.name,
                    'data': [0 for _ in range(months)],
                    'borderColor': category.color,
                    'backgroundColor': category.color
                }

            months_list_index = abs((month.year - start_date.year) * 12 + (month.month - start_date.month - 1))
            datasets[category.name]['data'][months_list_index] = amount

        return {
            'labels': list(map(lambda m: month_name[(m % 12) + 1],
                               range(start_date.month, start_date.month + months))),
            'datasets': list(datasets.values())
        }

    @staticmethod
    def _calculate_start_date(end_date, months):
        # calculate how many years and months are in given months
        sign = int(copysign(1, months))
        div, mod = divmod(months * sign, 12)

        year = end_date.year - (div * sign)
        month = end_date.month - (mod * sign)
        if month < 1:
            year -= 1
            month += 12

        return end_date.replace(month=month, year=year)


api.add_resource(QuickHistoryChartResource, '/history-chart/<int:months>')


class CategoriesChartResource(Resource):

    @jwt_required()
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

        expenses = expenses \
            .join(Category, Expense.category_id == Category.id) \
            .with_entities(Category.name, Category.background_color, func.sum(Expense.amount).label('total_amount')) \
            .group_by(Category) \
            .order_by(desc('total_amount')) \
            .all()

        labels, background_colors, amounts = list(), list(), list()
        if expenses:
            labels, background_colors, amounts = zip(*expenses)

        return {
            'chart': {
                'labels': labels,
                'datasets': [{
                    'data': amounts,
                    'backgroundColor': background_colors
                }]
            },
            'total_amount': round(sum(amounts), 2)
        }


api.add_resource(CategoriesChartResource,
                 '/categories-chart/',
                 '/categories-chart/<datetime:start_date>/<datetime:end_date>/<int:category>/')
