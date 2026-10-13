from django import forms

from ..models import Course


class CourseCreateForm(forms.ModelForm):
    short_desc = forms.CharField(max_length=280, required=False)
    duration_weeks = forms.IntegerField(min_value=1, max_value=52, required=False, initial=12)
    capacity_mode = forms.ChoiceField(choices=(("unlimited", "Unlimited"), ("limited", "Limited")))
    capacity = forms.IntegerField(min_value=1, required=False)
    action = forms.ChoiceField(choices=(("publish", "Publish"), ("draft", "Draft")))

    class Meta:
        model = Course
        fields = (
            "title", "description", "category", "tags", "level",
            "duration_weeks", "enrollment_type", "allow_discussions",
            "thumbnail", "intro_video",
        )

    def clean_tags(self):
        tags = self.cleaned_data.get("tags", "")
        unique = {}
        for tag in tags.split(","):
            cleaned = tag.strip()
            if cleaned:
                unique.setdefault(cleaned.casefold(), cleaned)
        return ", ".join(list(unique.values())[:12])

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("capacity_mode") == "limited" and not cleaned.get("capacity"):
            self.add_error("capacity", "Provide a capacity for limited enrollment.")
        return cleaned

    def save(self, *, instructor, commit=True):
        course = super().save(commit=False)
        description = self.cleaned_data.get("description", "")
        course.short_description = self.cleaned_data.get("short_desc") or description[:280]
        course.duration_weeks = self.cleaned_data.get("duration_weeks") or 12
        course.max_students = self.cleaned_data.get("capacity") if self.cleaned_data["capacity_mode"] == "limited" else None
        course.is_published = self.cleaned_data["action"] == "publish"
        course.instructor = instructor
        if commit:
            course.save()
        return course


class CourseReviewForm(forms.Form):
    course_rating = forms.IntegerField(min_value=1, max_value=5)
    instructor_rating = forms.IntegerField(min_value=1, max_value=5)
    comment = forms.CharField(required=False, max_length=2000, widget=forms.Textarea)
