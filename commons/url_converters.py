from werkzeug.routing import BaseConverter, ValidationError

from datetime import datetime


class DatetimeConverter(BaseConverter):

    def to_python(self, value):
        try:
            return datetime.fromisoformat(value)

        except ValueError as datetime_conversion_error:
            raise ValidationError(datetime_conversion_error)

    def to_url(self, value):
        if isinstance(value, datetime):
            return value.isoformat()

        return value
