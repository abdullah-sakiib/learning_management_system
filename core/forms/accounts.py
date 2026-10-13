from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from ..models import Profile


User = get_user_model()


class RegistrationForm(forms.Form):
    role = forms.ChoiceField(
        choices=(
            (Profile.ROLE_STUDENT, "Student"),
            (Profile.ROLE_INSTRUCTOR, "Instructor"),
        ),
        initial=Profile.ROLE_STUDENT,
    )
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)
    terms = forms.BooleanField()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        if password1:
            validate_password(password1)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        base_username = email.split("@", 1)[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user = User.objects.create_user(
            username=username,
            email=email,
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
        )
        Profile.objects.create(user=user, role=self.cleaned_data["role"])
        return user


class ProfileGeneralForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    city = forms.CharField(max_length=120, required=False)
    country = forms.CharField(max_length=120, required=False)
    bio = forms.CharField(max_length=500, required=False, widget=forms.Textarea)
    avatar = forms.ImageField(required=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("This email is already used by another account.")
        return email
