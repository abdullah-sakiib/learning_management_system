from django.urls import path

from ..views import assessments


urlpatterns = [
    path("assignments/", assessments.assignments, name="assignments"),
    path("grades/", assessments.grades, name="grades"),
    path("quiz/", assessments.quiz, name="quiz"),
    path("quiz/<int:quiz_id>/take/", assessments.quiz_take, name="quiz_take"),
]
