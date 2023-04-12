from flask import request

from functools import wraps
from types import SimpleNamespace


def req_parser(request_parser, strict=True):
    def decorator(f):
        @wraps(f)
        def inner(self, *args, **kwargs):
            if request.data or request.args:  # bad request on empty request ArgParse workaround
                parsed_args = request_parser.parse_args(strict=strict)

                # empty values ArgParse workaround
                errors = dict()
                for arg in request_parser.args:
                    if arg.name in parsed_args and arg.required and not parsed_args[arg.name]:
                        errors[arg.name] = arg.help

                if errors:
                    return {'message': errors}, 400

            else:
                # empty request body workaround
                # (make requests_parser assume a request with an empty json body and use arguments default values)
                parsed_args = request_parser.parse_args(req=SimpleNamespace(**{'unparsed_arguments': {}}),
                                                        strict=strict)

            return f(self, parsed_args, *args, **kwargs)

        return inner
    return decorator
