"""Reusable OpenAPI shapes. Documentation only; runtime validation stays in services."""
from drf_spectacular.utils import OpenApiParameter

TEXT = {'type': 'string'}
INTEGER = {'type': 'integer'}
BOOLEAN = {'type': 'boolean'}
DATE = {'type': 'string', 'format': 'date'}
DATETIME = {'type': 'string', 'format': 'date-time'}
FILE = {'type': 'string', 'format': 'binary'}
JSON = {'type': 'object', 'additionalProperties': {}}


def nullable(shape):
    return {**shape, 'nullable': True}


def array(shape):
    return {'type': 'array', 'items': shape}


def obj(properties, required=None):
    fields = list(properties) if required is None else required
    return {'type': 'object', 'properties': properties, **({'required': fields} if fields else {})}


def page(resource):
    return obj({'count': INTEGER, 'page': INTEGER, 'page_size': INTEGER, 'results': array(resource)})


def responses(success, status=200):
    # Records/owned endpoints have both Django and DRF validation error variants.
    error = obj({'detail': TEXT, 'code': TEXT, 'errors': {}}, required=[])
    return {status: success, **{code: error for code in (400, 401, 403, 404, 409, 503)}}


PAGINATION = [OpenApiParameter('page', int), OpenApiParameter('page_size', int)]
