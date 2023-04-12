from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime

from app import db


class Share(db.Model):

    shared_by_user_id = db.Column(db.BigInteger, db.ForeignKey('user.id'), primary_key=True)  # me
    shared_with_user_id = db.Column(db.BigInteger, db.ForeignKey('user.id'), primary_key=True)  # others

    # user *--* relationship
    shared_by = db.relationship('User', back_populates='shared_by', foreign_keys=[shared_by_user_id])
    shared_with = db.relationship('User', back_populates='shared_with', foreign_keys=[shared_with_user_id])


class User(db.Model):

    @staticmethod
    def update_timestamp(context):
        context.get_current_parameters()['updated_timestamp'] = datetime.now()

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    email = db.Column(db.String(25), nullable=False, unique=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password_hash = db.Column(db.String(128), name='password', nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_timestamp = db.Column(db.DateTime, default=datetime.now)
    updated_timestamp = db.Column(db.DateTime, nullable=True, onupdate=update_timestamp)

    # share *--* relationship
    shared_by = db.relationship('Share', foreign_keys=Share.shared_by_user_id)
    shared_with = db.relationship('Share', foreign_keys=Share.shared_with_user_id)

    # category 1--* relationship
    categories = db.relationship('Category', back_populates='user')

    # expense 1--* relationship
    expenses = db.relationship('Expense', back_populates='user')

    @property
    def password(self):
        raise AttributeError('password is write-only')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)


class Category(db.Model):

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(20), nullable=False)
    limit = db.Column(db.Float, default=0)
    background_color = db.Column(db.String(7), name='color', nullable=False)
    text_color = db.Column(db.String(7), nullable=False)
    active = db.Column(db.Boolean, default=True)

    # user 1--* relationship
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id'))
    user = db.relationship('User', back_populates='categories')

    # expenses 1--* relationship
    expenses = db.relationship('Expense', back_populates='category')

    @property
    def color(self):
        return self.background_color

    @color.setter
    def color(self, value):
        self.background_color = value

        # also calculate and set the text_color
        color = value.lstrip('#')
        match len(color):
            case 3:
                r, g, b = color

            case 6:
                r, g, b = [int(color[i: i + 2], 16) for i in range(0, 6, 2)]

            case _:
                self.text_color = '#ffffff'
                return

                # set the color text based in the result of perceived brightness formula
        self.text_color = '#ffffff' if (0.2126 * r + 0.7152 * g + 0.0722 * b) <= 128 else '#000000'


class Expense(db.Model):

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    description = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.now)
    amount = db.Column(db.Float, nullable=False)
    paid = db.Column(db.Boolean, default=True)
    is_favorite = db.Column(db.Boolean, default=False)
    favorite_order = db.Column(db.Integer, nullable=True)

    # user 1--* relationship
    user_id = db.Column(db.BigInteger, db.ForeignKey('user.id'))
    user = db.relationship('User', back_populates='expenses')

    # category 1--* relationship
    category_id = db.Column(db.BigInteger, db.ForeignKey('category.id'))
    category = db.relationship('Category', back_populates='expenses')

    # self 1--1 relationship
    parent_id = db.Column(db.BigInteger, db.ForeignKey('expense.id'), nullable=True)
    children = db.relationship('Expense', cascade='all, delete')

    @property
    def is_shared(self):
        return any(self.children) or self.parent_id is not None

    @property
    def is_owner(self):
        return not self.parent_id

    @staticmethod
    def get_user_expenses_date_interval(user_id, start_date, end_date, category=None):
        if category:
            if isinstance(category, Category):
                category = category.id

            return Expense.query.filter(Expense.user_id == user_id,
                                        Expense.timestamp >= start_date,
                                        Expense.timestamp <= end_date,
                                        Expense.category_id == category) \
                .join(Category, Expense.category_id == Category.id)

        return Expense.query.filter(Expense.user_id == user_id,
                                    Expense.timestamp >= start_date,
                                    Expense.timestamp <= end_date) \
            .join(Category, Expense.category_id == Category.id)

    def create_shared_expense(self, share_with_user, amount, paid=False):
        if isinstance(share_with_user, User):
            share_with_user = share_with_user.id

        if not Share.query \
                .join(User, Share.shared_with_user_id == User.id) \
                .filter(Share.shared_by_user_id == self.user_id,
                        Share.shared_with_user_id == share_with_user,
                        User.active).count():
            raise PermissionError(f'{self.user_id} has no permission to share expenses with {share_with_user} '
                                  f'or user is disabled')

        return Expense(user_id=share_with_user,
                       description=self.description,
                       timestamp=self.timestamp,
                       amount=amount,
                       paid=paid,
                       parent_id=self.id)
