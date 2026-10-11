from controllers.common import ok
from services import my_requests


def list_mine():
    return ok(my_requests.list_mine())
