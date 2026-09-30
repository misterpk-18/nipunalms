from controllers.common import ok
from services import student_home, trainer_workspace


def my_home():
    return ok(student_home.my_home())


def trainer_today():
    return ok(trainer_workspace.today())
