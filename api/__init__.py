from flask import Blueprint

from api.auth.routes import auth_blueprint
from api.category.routes import category_blueprint
from api.charts.routes import charts_blueprint
from api.datatables.routes import datatables_blueprint
from api.expense.routes import expense_blueprint
from api.user.routes import user_blueprint


api_blueprint = Blueprint('api', __name__)

api_blueprint.register_blueprint(auth_blueprint)
api_blueprint.register_blueprint(category_blueprint)
api_blueprint.register_blueprint(charts_blueprint)
api_blueprint.register_blueprint(datatables_blueprint)
api_blueprint.register_blueprint(expense_blueprint)
api_blueprint.register_blueprint(user_blueprint)
