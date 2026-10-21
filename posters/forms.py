"""The presenter's form, and the forms an admin uses to make a link and approve a poster."""

from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from PIL import Image

from accounts.forms import style_widgets
from accounts.validators import validate_web_url
from events.models import Event

from .models import Platform, TalkPoster

PHOTO_MAX_BYTES = 10 * 1024 * 1024
PHOTO_MIN_SIDE = 400
PRESENTER_FIELDS = ("title", "summary", "about", "speaker_name", "speaker_tag", "photo")


def printable(value):
    """Refuse characters the poster's fonts cannot draw.

    The fonts cover Latin letters (accents included) and ordinary punctuation.
    Anything else, Korean or an emoji for example, would come out as empty
    boxes on a poster people have already shared, so it is caught here instead.
    """
    missing = list(dict.fromkeys(
        ch for ch in value
        if not (ord(ch) < 0x250 or 0x1E00 <= ord(ch) <= 0x1EFF
                or 0x2010 <= ord(ch) <= 0x2027 or ord(ch) == 0x20AC)
    ))
    if missing:
        raise ValidationError(
            "The poster can only print Latin letters, so it cannot show %(chars)s. Please "
            "write this in English.", params={"chars": " ".join(missing)})


def one_line(value):
    return " ".join(value.split())


def check_photo(photo, talk):
    """A new upload must be a real photo, not huge, and big enough to look sharp on the poster."""
    if not photo or photo == talk.photo:
        return photo
    if photo.size > PHOTO_MAX_BYTES:
        raise ValidationError("That photo is bigger than 10 MB. Please choose a smaller one.")
    photo.seek(0)
    try:
        with Image.open(photo) as picture:
            kind, (width, height) = picture.format, picture.size
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("That file is not a photo we can read. Please send a JPEG "
                              "or PNG.") from exc
    if kind not in {"JPEG", "PNG", "WEBP", "MPO"}:
        raise ValidationError("Please send the photo as a JPEG or PNG.")
    if min(width, height) < PHOTO_MIN_SIDE:
        raise ValidationError(
            f"That photo is only {width}×{height} pixels, so it would look blurred. Please "
            f"send one at least {PHOTO_MIN_SIDE} pixels on each side.")
    photo.seek(0)
    return photo


class PresenterForm(forms.ModelForm):
    class Meta:
        model = TalkPoster
        fields = PRESENTER_FIELDS
        labels = {
            "title": "Title of your talk",
            "summary": "Short description",
            "about": "About the talk",
            "speaker_name": "Your name",
            "speaker_tag": "Who you are",
            "photo": "Your photo",
        }
        help_texts = {
            "title": "Short and clear works best, for example 'What makes a designer in 2026?'",
            "summary": "One or two sentences under the title, for example 'A look at the future "
                       "of design. We'll explore the mindset, skills, tools, and trends that "
                       "will define designers in 2026 and beyond.'",
            "about": "What people will get from it, for example 'After the session, the "
                     "audience will know where to start and where design is going.'",
            "speaker_name": "As it should appear on the poster.",
            "speaker_tag": "A few words for the badge under your name, for example "
                           "'KDU Alumni', 'KDU Student' or 'Software engineer'.",
            "photo": "A clear photo of you, facing the camera, with your head near the top. "
                     "JPEG or PNG, up to 10 MB. It will be cropped to a tall rectangle.",
        }
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 3}),
            "about": forms.Textarea(attrs={"rows": 3}),
            "photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in PRESENTER_FIELDS:
            self.fields[name].required = True
        # Someone sent a new link to fix their details keeps the photo they
        # sent before unless they choose another.
        if self.instance.photo:
            self.fields["photo"].required = False
            self.fields["photo"].help_text = ("You sent a photo before. Choose a new one only if "
                                              "you want to change it.")
        style_widgets(self)

    def _clean_text(self, name):
        value = one_line(self.cleaned_data.get(name, ""))
        printable(value)
        return value

    def clean_title(self):
        return self._clean_text("title")

    def clean_summary(self):
        return self._clean_text("summary")

    def clean_about(self):
        return self._clean_text("about")

    def clean_speaker_name(self):
        return self._clean_text("speaker_name")

    def clean_speaker_tag(self):
        return self._clean_text("speaker_tag")

    def clean_photo(self):
        return check_photo(self.cleaned_data.get("photo"), self.instance)


class TalkPosterAdminForm(forms.ModelForm):
    """The admin's form. Picking an event fills in its date and time."""

    class Meta:
        model = TalkPoster
        fields = ("event", "label", "starts_at", "ends_at", "platform", "place", "place_detail",
                  "link_expires_at") + PRESENTER_FIELDS
        # No "clear" box: a poster cannot be drawn without a photo.
        widgets = {"photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("starts_at", "ends_at"):
            if name in self.fields:
                self.fields[name].required = False
                self.fields[name].help_text = "Filled in from the event if you pick one."

    def clean(self):
        data = super().clean()
        event = data.get("event")
        if event:
            data["starts_at"] = data.get("starts_at") or event.starts_at
            data["ends_at"] = data.get("ends_at") or event.ends_at
        missing = {name: "Pick an event above, or fill this in."
                   for name in ("starts_at", "ends_at") if not data.get(name)}
        if missing:
            raise ValidationError(missing)
        if data["ends_at"] <= data["starts_at"]:
            raise ValidationError({"ends_at": "The talk has to end after it starts."})
        if data.get("platform") == Platform.IN_PERSON and not data.get("place"):
            self.add_error("place", "Say where, for example 'Engineering building, room 301'.")
        for name in ("label", "place", "place_detail", "title", "summary", "about",
                     "speaker_name", "speaker_tag"):
            if data.get(name):
                try:
                    printable(data[name])
                except ValidationError as error:
                    self.add_error(name, error)
        return data

    def clean_photo(self):
        return check_photo(self.cleaned_data.get("photo"), self.instance)


class ApproveForm(forms.Form):
    ATTACH, CREATE = "attach", "create"

    choice = forms.ChoiceField(
        label="Where should the poster go?",
        choices=[(ATTACH, "On an event that already exists"),
                 (CREATE, "On a new event made from this poster")],
        widget=forms.RadioSelect,
    )
    event = forms.ModelChoiceField(
        queryset=Event.objects.none(), required=False, label="Event",
        help_text="Upcoming events first.")
    status = forms.ChoiceField(
        label="The new event is", required=False,
        choices=[(Event.Status.DRAFT, "A draft, for me to finish before anyone sees it"),
                 (Event.Status.PUBLISHED, "Published straight away")],
        initial=Event.Status.DRAFT,
    )
    online_url = forms.URLField(
        label="Online link for the new event", required=False,
        validators=[validate_web_url],
        help_text="Optional. The video-call link. The site shows it only to people who "
                  "registered.")

    def __init__(self, *args, talk, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.now()
        self.fields["event"].queryset = Event.objects.exclude(status=Event.Status.CANCELLED) \
            .filter(ends_at__gte=now - timedelta(days=30)).order_by("starts_at")
        self.initial.setdefault("choice", self.ATTACH if talk.event_id else self.CREATE)
        self.initial.setdefault("event", talk.event_id)

    def clean(self):
        data = super().clean()
        if data.get("choice") == self.ATTACH and not data.get("event"):
            self.add_error("event", "Pick the event to put the poster on.")
        return data
