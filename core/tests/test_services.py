from django.test import TestCase

from ..models import Enrollment, Profile, Quiz, QuizAttempt, QuizQuestion
from ..services.assessments import submit_quiz_attempt
from ..services.enrollments import approve_enrollment
from .factories import create_course, create_user


class EnrollmentServiceTests(TestCase):
    def test_approve_enrollment_updates_pending_record(self):
        instructor = create_user(username="service-inst", role=Profile.ROLE_INSTRUCTOR)
        student = create_user(username="service-student", role=Profile.ROLE_STUDENT)
        course = create_course(instructor=instructor)
        enrollment = Enrollment.objects.create(
            student=student,
            course=course,
            status=Enrollment.STATUS_PENDING,
        )

        self.assertTrue(approve_enrollment(enrollment))
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, Enrollment.STATUS_APPROVED)
        self.assertIsNotNone(enrollment.approved_at)


class AssessmentServiceTests(TestCase):
    def test_submit_quiz_attempt_scores_and_stores_answers(self):
        instructor = create_user(username="quiz-inst", role=Profile.ROLE_INSTRUCTOR)
        student = create_user(username="quiz-student", role=Profile.ROLE_STUDENT)
        course = create_course(instructor=instructor)
        quiz = Quiz.objects.create(course=course, title="Basics", created_by=instructor)
        question = QuizQuestion.objects.create(
            quiz=quiz,
            question_text="Two plus two?",
            correct_answer="Four",
            marks=5,
        )
        attempt = QuizAttempt.objects.create(quiz=quiz, student=student)

        score = submit_quiz_attempt(attempt, [question], {question.id: "four"})

        attempt.refresh_from_db()
        response = attempt.responses.get(question=question)
        self.assertEqual(score, 5)
        self.assertEqual(attempt.score, 5)
        self.assertTrue(response.is_correct)
        self.assertEqual(response.answer_text, "four")
