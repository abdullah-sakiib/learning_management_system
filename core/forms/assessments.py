from django import forms


class AssignmentSubmissionForm(forms.Form):
    assignment_id = forms.IntegerField(required=False, min_value=1)
    assignment_title = forms.CharField(required=False, max_length=200)
    submission = forms.FileField()
    comment = forms.CharField(required=False, max_length=2000, widget=forms.Textarea)

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("assignment_id") and not cleaned.get("assignment_title"):
            raise forms.ValidationError("Select an assignment.")
        return cleaned


class QuizCreateForm(forms.Form):
    title = forms.CharField(max_length=200)
    course_id = forms.IntegerField(min_value=1)
    total_marks = forms.IntegerField(min_value=1, initial=100)
    time_limit_minutes = forms.IntegerField(min_value=1, initial=30)
