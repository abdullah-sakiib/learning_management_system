from django.utils import timezone

from ..models import QuizResponse


def submit_quiz_attempt(attempt, questions, answers):
    """Score and persist a quiz attempt from a question-id to answer mapping."""
    total_score = 0
    for question in questions:
        selected_answer = answers.get(question.id, "").strip()
        is_correct = bool(selected_answer and question.correct_answer) and (
            selected_answer.casefold() == question.correct_answer.strip().casefold()
        )
        awarded_marks = question.marks if is_correct else 0
        QuizResponse.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={
                "answer_text": selected_answer,
                "is_correct": is_correct,
                "awarded_marks": awarded_marks,
            },
        )
        total_score += awarded_marks

    attempt.score = total_score
    attempt.submitted_at = timezone.now()
    attempt.save(update_fields=["score", "submitted_at"])
    return total_score
