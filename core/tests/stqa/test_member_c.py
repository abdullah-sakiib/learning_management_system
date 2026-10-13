from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from core.forms.assessments import AssignmentSubmissionForm, QuizCreateForm
from core.models import (
    Assignment,
    Enrollment,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Submission,
)
from core.services.assessments import submit_quiz_attempt


pytestmark = [pytest.mark.django_db, pytest.mark.member_c]


QUIZ_FORM_BOUNDARIES = [
    pytest.param("title", "", False, id="C-TC-001-quiz-title-empty"),
    pytest.param("title", "x", True, id="C-TC-002-quiz-title-min"),
    pytest.param("title", "x" * 200, True, id="C-TC-003-quiz-title-max"),
    pytest.param("title", "x" * 201, False, id="C-TC-004-quiz-title-above-max"),
    pytest.param("total_marks", 0, False, id="C-TC-005-total-marks-below-min"),
    pytest.param("total_marks", 1, True, id="C-TC-006-total-marks-min"),
    pytest.param("total_marks", 2, True, id="C-TC-007-total-marks-above-min"),
    pytest.param("time_limit_minutes", 0, False, id="C-TC-008-time-limit-below-min"),
    pytest.param("time_limit_minutes", 1, True, id="C-TC-009-time-limit-min"),
    pytest.param("time_limit_minutes", 2, True, id="C-TC-010-time-limit-above-min"),
]


@pytest.mark.unit
@pytest.mark.bva
@pytest.mark.parametrize(("field", "value", "expected"), QUIZ_FORM_BOUNDARIES)
def test_quiz_create_form_boundaries(field, value, expected):
    data = {"title": "Quiz", "course_id": 1, "total_marks": 100, "time_limit_minutes": 30}
    data[field] = value
    assert QuizCreateForm(data=data).is_valid() is expected


SUBMISSION_CLASSES = [
    pytest.param("neither", True, 10, False, id="C-TC-011-no-assignment-reference"),
    pytest.param("id", True, 10, True, id="C-TC-012-id-reference-with-file"),
    pytest.param("title", True, 10, True, id="C-TC-013-title-reference-with-file"),
    pytest.param("id", False, 10, False, id="C-TC-014-missing-submission-file"),
    pytest.param("zero-id", True, 10, False, id="C-TC-015-zero-assignment-id"),
    pytest.param("id", True, 0, True, id="C-TC-016-empty-comment"),
    pytest.param("id", True, 2000, True, id="C-TC-017-comment-max"),
    pytest.param("id", True, 2001, False, id="C-TC-018-comment-above-max"),
]


@pytest.mark.unit
@pytest.mark.equivalence
@pytest.mark.parametrize(("reference", "has_file", "comment_length", "expected"), SUBMISSION_CLASSES)
def test_assignment_submission_form_classes(reference, has_file, comment_length, expected):
    data = {"comment": "x" * comment_length}
    if reference == "id":
        data["assignment_id"] = 1
    elif reference == "zero-id":
        data["assignment_id"] = 0
    elif reference == "title":
        data["assignment_title"] = "Assignment"
    files = {"submission": SimpleUploadedFile("answer.txt", b"answer")} if has_file else {}
    assert AssignmentSubmissionForm(data=data, files=files).is_valid() is expected


SCORING_PATHS = [
    pytest.param("Four", "Four", True, 5, id="C-TC-019-exact-correct-answer"),
    pytest.param("four", "Four", True, 5, id="C-TC-020-case-insensitive-answer"),
    pytest.param("  Four  ", "Four", True, 5, id="C-TC-021-answer-whitespace-trimmed"),
    pytest.param("Five", "Four", False, 0, id="C-TC-022-incorrect-answer"),
    pytest.param("", "Four", False, 0, id="C-TC-023-blank-answer"),
    pytest.param(None, "Four", False, 0, id="C-TC-024-missing-answer-key"),
    pytest.param("True", "true", True, 5, id="C-TC-025-true-false-case-variant"),
    pytest.param("anything", "", False, 0, id="C-TC-026-question-without-correct-answer"),
]


@pytest.mark.unit
@pytest.mark.basis_path
@pytest.mark.parametrize(("selected", "correct", "is_correct", "score"), SCORING_PATHS)
def test_quiz_scoring_paths(student, course, selected, correct, is_correct, score):
    quiz = Quiz.objects.create(course=course, title="Scoring", created_by=course.instructor)
    question = QuizQuestion.objects.create(
        quiz=quiz,
        question_text="Question",
        correct_answer=correct,
        marks=5,
    )
    attempt = QuizAttempt.objects.create(quiz=quiz, student=student)
    answers = {} if selected is None else {question.id: selected}

    result = submit_quiz_attempt(attempt, [question], answers)

    response = attempt.responses.get(question=question)
    assert result == score
    assert response.is_correct is is_correct
    assert response.awarded_marks == score


MODEL_CONSTRAINTS = [
    pytest.param("assignment-score-zero", False, id="C-TC-027-assignment-score-below-min"),
    pytest.param("assignment-score-one", True, id="C-TC-028-assignment-score-min"),
    pytest.param("quiz-total-zero", False, id="C-TC-029-quiz-total-below-min"),
    pytest.param("quiz-time-zero", False, id="C-TC-030-quiz-time-below-min"),
]


@pytest.mark.unit
@pytest.mark.bva
@pytest.mark.parametrize(("scenario", "expected_valid"), MODEL_CONSTRAINTS)
def test_assessment_model_boundaries(course, scenario, expected_valid):
    if scenario.startswith("assignment"):
        value = 0 if scenario.endswith("zero") else 1
        obj = Assignment(course=course, title="Assignment", max_score=value)
    else:
        obj = Quiz(
            course=course,
            title="Quiz",
            total_marks=0 if scenario == "quiz-total-zero" else 100,
            time_limit_minutes=0 if scenario == "quiz-time-zero" else 30,
        )
    if expected_valid:
        obj.full_clean()
    else:
        with pytest.raises(ValidationError):
            obj.full_clean()


@pytest.mark.unit
def test_c_tc_031_duplicate_quiz_attempt_is_rejected(student, course):
    quiz = Quiz.objects.create(course=course, title="Unique attempt")
    QuizAttempt.objects.create(quiz=quiz, student=student)
    with pytest.raises(IntegrityError):
        QuizAttempt.objects.create(quiz=quiz, student=student)


@pytest.mark.unit
def test_c_tc_032_duplicate_assignment_submission_is_rejected(student, course):
    assignment = Assignment.objects.create(course=course, title="Unique submission")
    Submission.objects.create(assignment=assignment, student=student, file="first.txt")
    with pytest.raises(IntegrityError):
        Submission.objects.create(assignment=assignment, student=student, file="second.txt")


ASSIGNMENT_VIEW_PATHS = [
    pytest.param("anonymous", 302, 0, id="C-TC-033-anonymous-submission"),
    pytest.param("instructor", 302, 0, id="C-TC-034-instructor-cannot-submit"),
    pytest.param("not-enrolled", 302, 0, id="C-TC-035-non-enrolled-student"),
    pytest.param("first", 302, 1, id="C-TC-036-first-submission"),
    pytest.param("replace", 302, 1, id="C-TC-037-replace-submission"),
    pytest.param("future", 302, 0, id="C-TC-038-future-assignment"),
]


@pytest.mark.integration
@pytest.mark.decision_table
@pytest.mark.parametrize(("scenario", "expected_status", "expected_count"), ASSIGNMENT_VIEW_PATHS)
def test_assignment_submission_paths(
    client, settings, tmp_path, student, instructor, course, scenario, expected_status, expected_count
):
    settings.MEDIA_ROOT = tmp_path
    assignment = Assignment.objects.create(
        course=course,
        title="Lab Report",
        created_by=instructor,
        publish_at=timezone.now() + timedelta(days=1) if scenario == "future" else None,
    )
    if scenario in {"first", "replace", "future"}:
        Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_APPROVED)
    if scenario == "replace":
        Submission.objects.create(assignment=assignment, student=student, file="old.txt", comment="old")
    if scenario == "anonymous":
        pass
    elif scenario == "instructor":
        client.force_login(instructor)
    else:
        client.force_login(student)

    response = client.post(
        reverse("assignments"),
        {
            "assignment_id": assignment.id,
            "comment": "replacement" if scenario == "replace" else "answer",
            "submission": SimpleUploadedFile("answer.txt", b"answer"),
        },
    )

    assert response.status_code == expected_status
    assert Submission.objects.filter(student=student, assignment=assignment).count() == expected_count
    if scenario == "replace":
        assert Submission.objects.get(student=student, assignment=assignment).comment == "replacement"


QUIZ_TAKE_PATHS = [
    pytest.param("not-enrolled", 302, 0, id="C-TC-039-not-enrolled-quiz"),
    pytest.param("no-questions", 302, 0, id="C-TC-040-quiz-without-questions"),
    pytest.param("correct", 302, 5, id="C-TC-041-correct-quiz-submission"),
    pytest.param("repeated", 302, 5, id="C-TC-042-repeated-quiz-submission"),
    pytest.param("unpublished", 404, 0, id="C-TC-043-unpublished-quiz"),
]


@pytest.mark.integration
@pytest.mark.basis_path
@pytest.mark.parametrize(("scenario", "expected_status", "expected_score"), QUIZ_TAKE_PATHS)
def test_quiz_take_paths(client, student, course, scenario, expected_status, expected_score):
    quiz = Quiz.objects.create(
        course=course,
        title="Attempt Quiz",
        created_by=course.instructor,
        is_published=scenario != "unpublished",
    )
    if scenario != "not-enrolled":
        Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_APPROVED)
    question = None
    if scenario not in {"no-questions", "unpublished"}:
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text="2 + 2",
            correct_answer="4",
            marks=5,
        )
    if scenario == "repeated":
        attempt = QuizAttempt.objects.create(quiz=quiz, student=student, score=5, submitted_at=timezone.now())
    client.force_login(student)
    data = {f"answer_{question.id}": "4"} if question else {}

    response = client.post(reverse("quiz_take", args=[quiz.id]), data)

    assert response.status_code == expected_status
    attempt = QuizAttempt.objects.filter(quiz=quiz, student=student).first()
    if attempt:
        attempt.refresh_from_db()
        assert attempt.score == expected_score


GRADING_PATHS = [
    pytest.param("grade", "80", Submission.STATUS_GRADED, "80.00", id="C-TC-044-valid-grade"),
    pytest.param("resubmit", "50", Submission.STATUS_SUBMITTED, "50.00", id="C-TC-045-request-resubmission"),
    pytest.param("grade", "invalid", Submission.STATUS_SUBMITTED, None, id="C-TC-046-invalid-score"),
    pytest.param("grade", "101", Submission.STATUS_SUBMITTED, None, id="C-TC-047-score-above-maximum"),
]


@pytest.mark.integration
@pytest.mark.decision_table
@pytest.mark.parametrize(("action", "score", "expected_status", "expected_score"), GRADING_PATHS)
def test_grading_paths(client, instructor, student, course, action, score, expected_status, expected_score):
    assignment = Assignment.objects.create(course=course, title="Grade me", created_by=instructor, max_score=100)
    submission = Submission.objects.create(assignment=assignment, student=student, file="answer.txt")
    client.force_login(instructor)

    response = client.post(
        reverse("instructor_submissions"),
        {"submission_id": submission.id, "score": score, "feedback": "Feedback", "action": action},
    )

    assert response.status_code == 302
    submission.refresh_from_db()
    assert submission.status == expected_status
    if expected_score is None:
        assert submission.score is None
    else:
        assert str(submission.score) == expected_score


QUIZ_EDIT_PATHS = [
    pytest.param("meta-clamp", 0, id="C-TC-048-quiz-meta-clamps-positive-values"),
    pytest.param("invalid-mcq", 0, id="C-TC-049-mcq-requires-two-options"),
    pytest.param("true-false", 1, id="C-TC-050-true-false-default-answer"),
]


@pytest.mark.integration
@pytest.mark.basis_path
@pytest.mark.parametrize(("scenario", "expected_questions"), QUIZ_EDIT_PATHS)
def test_instructor_quiz_edit_paths(client, instructor, course, scenario, expected_questions):
    quiz = Quiz.objects.create(course=course, title="Editable", created_by=instructor)
    client.force_login(instructor)
    if scenario == "meta-clamp":
        data = {
            "form_type": "quiz_meta",
            "title": "Updated",
            "total_marks": "0",
            "time_limit_minutes": "0",
            "is_published": "on",
        }
    elif scenario == "invalid-mcq":
        data = {
            "form_type": "add_question",
            "question_text": "Choose",
            "question_type": QuizQuestion.TYPE_MCQ,
            "options": "Only one",
            "correct_answer": "Only one",
        }
    else:
        data = {
            "form_type": "add_question",
            "question_text": "Statement",
            "question_type": QuizQuestion.TYPE_TRUE_FALSE,
            "correct_answer": "",
        }

    response = client.post(reverse("instructor_edit_quiz", args=[quiz.id]), data)

    assert response.status_code == 302
    assert quiz.questions.count() == expected_questions
    if scenario == "meta-clamp":
        quiz.refresh_from_db()
        assert quiz.total_marks == 1
        assert quiz.time_limit_minutes == 1
    elif scenario == "true-false":
        assert quiz.questions.get().correct_answer == "True"

