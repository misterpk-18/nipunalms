from controllers.common import ok
from services import student_work


def my_work():
    return ok(student_work.get_work())
