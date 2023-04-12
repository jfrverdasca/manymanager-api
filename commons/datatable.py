from flask import request
from sqlalchemy.sql import cast, desc, or_
from sqlalchemy.sql.sqltypes import String

from functools import wraps
from types import SimpleNamespace


def datatable_request_parser(default_ordered_column=None, default_order_direction=None):
    def decorator(f):
        @wraps(f)
        def inner(self, *args, **kwargs):
            page_length = request.args.get('length', 10, int)
            item_index_start = request.args.get('start', 0, int)

            if draw := request.args.get('draw', None, int):
                draw += 1

            # get datatable static attributes
            datatable_data = {
                'draw': draw,
                'ordered_column': request.args.get('order[0][column]', default_ordered_column, int),
                'order_direction': request.args.get('order[0][dir]', default_order_direction, str),
                'pagination_page': (item_index_start + page_length) / page_length if page_length > 0 else 1,
                'page_length': page_length,
                'item_start_index': item_index_start,
                'search_value': request.args.get('search[value]', '', str)
            }

            # get mutable attributes
            i = 0
            while True:
                try:
                    # column is searchable and orderable property
                    datatable_data[f'column_{i}_searchable'] = request.args[f'columns[{i}][searchable]'] == 'true'
                    datatable_data[f'column_{i}_orderable'] = request.args[f'columns[{i}][orderable]'] == 'true'

                except KeyError:
                    break

                i += 1

            self.datatable = SimpleNamespace(**datatable_data)

            response = f(self, *args, **kwargs)
            if 'draw' not in response:
                response['draw'] = self.datatable.draw

            if 'recordsFiltered' not in response:
                response['recordsFiltered'] = 0

            if 'recordsTotal' not in response:
                response['recordsTotal'] = len(response['data'])

            return response
        return inner
    return decorator


class DatatableHandler:

    COLUMNS = None

    datatable = None

    def handle_request(self, records):
        return self.paginate_records(self.order_records(self.filter_records(records)))

    def filter_records(self, records):
        search_parameters = list()
        if self.datatable.search_value:
            for i in self.COLUMNS:
                # check if column is searchable
                if getattr(self.datatable, f'column_{i}_searchable'):
                    database_column = self.COLUMNS[i]

                    search_parameters.append(cast(database_column, String).contains(self.datatable.search_value))

            return records.filter(or_(*search_parameters))

        return records

    def order_records(self, records):
        if self.datatable.ordered_column and \
                getattr(self.datatable, f'column_{self.datatable.ordered_column}_orderable'):
            database_column = self.COLUMNS[self.datatable.ordered_column]

            return records.order_by(desc(database_column)) \
                if self.datatable.order_direction == 'desc' \
                else records.order_by(database_column)

        return records

    def paginate_records(self, records):
        records_count = records.count()
        if self.datatable.page_length < 0:  # user wants to see all records
            self.datatable.page_length = records_count

        return records.paginate(page=self.datatable.pagination_page, per_page=self.datatable.page_length)

