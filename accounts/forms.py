"""The forms behind signing up, signing in and editing a profile."""

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils import timezone

from content.models import InterestArea

from .models import Member

UserModel = get_user_model()

CONSENT_ERROR = (
    "You have to accept the community rules, the terms and the privacy notice "
    "before you can have an account."
)


def style_widgets(form):
    """Give Django's widgets the class names this site's CSS actually uses.

    Doing it here rather than on every field declaration means a field added
    later is styled by default instead of quietly rendering unstyled.
    """
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxSelectMultiple):
            continue
        if isinstance(widget, forms.CheckboxInput | forms.RadioSelect):
            continue
        if isinstance(widget, forms.Textarea):
            widget.attrs.setdefault("class", "textarea")
            widget.attrs.setdefault("rows", 5)
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", "select")
        else:
            widget.attrs.setdefault("class", "input")


class SignUpForm(UserCreationForm):
    """Create a User and its Member together.

    The consent checkbox is required for the same reason it is required on the
    join form: the site promises that nobody joins without having been shown
    what they are agreeing to, and an unticked box has to actually stop the
    submission rather than merely look serious.
    """

    display_name = forms.CharField(
        label="Your name", max_length=120,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    email = forms.EmailField(
        label="Email address", max_length=160,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    student = forms.ChoiceField(
        label="Are you a Kyungdong University student?",
        choices=Member.Student.choices, required=False,
    )
    student_id = forms.CharField(
        label="Student ID", max_length=40, required=False,
        help_text="Only if you have one. It helps us confirm who you are.",
    )
    interests = forms.MultipleChoiceField(
        label="What are you interested in?", required=False,
        widget=forms.CheckboxSelectMultiple, choices=(),
    )
    accepted_documents = forms.BooleanField(
        label="I have read the community rules, the terms and the privacy notice, "
              "and I agree to them.",
        required=True, error_messages={"required": CONSENT_ERROR},
    )

    class Meta:
        model = UserModel
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Read from the database so the list matches the join form and the
        # rest of the site without being written down twice.
        self.fields["interests"].choices = [
            (area.name, area.name) for area in InterestArea.objects.live()
        ]
        # UserCreationForm brings a username field we do not want on screen;
        # the address becomes the username in save().
        self.fields.pop("username", None)
        self.fields["password1"].widget.attrs["autocomplete"] = "new-password"
        self.fields["password2"].widget.attrs["autocomplete"] = "new-password"
        style_widgets(self)

    def clean_email(self):
        address = self.cleaned_data["email"].strip()
        if UserModel.objects.filter(email__iexact=address).exists():
            raise forms.ValidationError(
                "There is already an account with this address. "
                "Sign in instead, or reset the password if you have forgotten it."
            )
        return address

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        # The stock user model requires a username and the admin, the password
        # reset and the session machinery all expect one. The address is it.
        user.username = self.cleaned_data["email"][:150]
        user.first_name = self.cleaned_data["display_name"][:150]
        user.save()

        Member.objects.create(
            user=user,
            display_name=self.cleaned_data["display_name"],
            student=self.cleaned_data.get("student", ""),
            student_id=self.cleaned_data.get("student_id", ""),
            interests=list(self.cleaned_data.get("interests") or []),
            accepted_documents=True,
            accepted_at=timezone.now(),
        )
        return user


class EmailLoginForm(AuthenticationForm):
    """The stock form, relabelled, because the field holds an address."""

    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That email address and password do not match an account.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)


class ProfileForm(forms.ModelForm):
    """What a member may change about themselves.

    Status and the internal notes are not here on purpose: those belong to the
    leadership team, and a form that let people set their own membership
    status would not be a review process.
    """

    interests = forms.MultipleChoiceField(
        label="What are you interested in?", required=False,
        widget=forms.CheckboxSelectMultiple, choices=(),
    )

    class Meta:
        model = Member
        fields = ("display_name", "student", "student_id", "interests",
                  "bio", "github_url", "linkedin_url")
        labels = {
            "bio": "A short introduction",
            "github_url": "GitHub",
            "linkedin_url": "LinkedIn",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interests"].choices = [
            (area.name, area.name) for area in InterestArea.objects.live()
        ]
        self.initial["interests"] = self.instance.interests or []
        style_widgets(self)
