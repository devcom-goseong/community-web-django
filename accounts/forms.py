"""The forms behind signing in and editing a profile.

There is no sign-up form: people join through the join form and the leadership
team creates the account when it accepts them (see accounts.services).
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm

from content.models import InterestArea

from .models import MAX_PROJECTS, Member, MemberProject
from .validators import validate_handle


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

    Status, approval and the internal notes are not here on purpose: those
    belong to the leadership team, and a form that let people set their own
    membership status would not be a review process.
    """

    interests = forms.MultipleChoiceField(
        label="What are you interested in?", required=False,
        widget=forms.CheckboxSelectMultiple, choices=(),
    )

    class Meta:
        model = Member
        fields = ("display_name", "handle", "profile_visibility", "bio", "interests",
                  "github_url", "linkedin_url", "student", "student_id")
        labels = {
            "display_name": "Your name",
            "handle": "Profile address",
            "profile_visibility": "Who can see your profile",
            "bio": "A short introduction",
            "github_url": "GitHub",
            "linkedin_url": "LinkedIn",
            "student": "Are you a Kyungdong University student?",
        }
        help_texts = {
            "display_name": "How your name appears to other members.",
            "handle": "Your profile lives at /members/<this>/. Lowercase letters, numbers and "
                      "hyphens. Changing it breaks any link to your profile you have already "
                      "shared.",
            "profile_visibility": "'Members' lists you in the members directory. 'Anyone with "
                                  "the link' also lets you share your profile outside the "
                                  "community, for example on a CV. Your email address and "
                                  "student details are never shown.",
            "bio": "Up to 600 characters. What you are learning, building, or looking for.",
            "student_id": "Only the leadership team sees this.",
        }
        widgets = {
            "profile_visibility": forms.RadioSelect,
            "bio": forms.Textarea(attrs={"rows": 4, "maxlength": 600}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interests"].choices = [
            (area.name, area.name) for area in InterestArea.objects.live()
        ]
        self.initial["interests"] = self.instance.interests or []
        self.fields["handle"].required = True
        style_widgets(self)

    def clean_display_name(self):
        name = " ".join(self.cleaned_data["display_name"].split())
        if not name:
            raise forms.ValidationError("Please enter a name.")
        return name

    def clean_handle(self):
        handle = self.cleaned_data["handle"].strip().lower()
        validate_handle(handle)
        taken = Member.objects.filter(handle__iexact=handle).exclude(pk=self.instance.pk)
        if taken.exists():
            raise forms.ValidationError("That address is already taken. Please choose another.")
        return handle

    def clean_interests(self):
        return list(self.cleaned_data.get("interests") or [])


class ProjectForm(forms.ModelForm):
    class Meta:
        model = MemberProject
        fields = ("title", "url", "description")
        labels = {"title": "What it is", "url": "Link", "description": "One sentence"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)


class BaseProjectFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        kept = [f for f in self.forms
                if f.has_changed() or f.instance.pk
                if not (self.can_delete and self._should_delete_form(f))]
        if len(kept) > MAX_PROJECTS:
            raise forms.ValidationError(f"You can list up to {MAX_PROJECTS} projects.")


ProjectFormSet = forms.inlineformset_factory(
    Member, MemberProject, form=ProjectForm, formset=BaseProjectFormSet,
    extra=1, max_num=MAX_PROJECTS, validate_max=True, can_delete=True,
)


class DirectoryFilterForm(forms.Form):
    q = forms.CharField(label="Search", required=False, max_length=80)
    interest = forms.ChoiceField(label="Interest", required=False, choices=())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interest"].choices = [("", "Any interest")] + [
            (area.name, area.name) for area in InterestArea.objects.live()
        ]
        self.fields["q"].widget.attrs["placeholder"] = "Name, handle or introduction"
        style_widgets(self)


class CloseAccountForm(forms.Form):
    password = forms.CharField(
        label="Your password", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
        help_text="To make sure it is really you.",
    )
    delete_applications = forms.BooleanField(
        label="Also delete anything I sent through the join form", required=False,
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        style_widgets(self)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError("That password is not right.")
        return password
