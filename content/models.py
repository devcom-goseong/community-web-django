"""Editable site content.

The shape of these models follows the shape of the pages. That is deliberate.
A single rich-text body per page would have been quicker to build and would
have destroyed the layout the first time somebody pasted into it. Here a
heading is a heading, a bullet list is a list, and an activity's cadence is a
field — so the design survives editing by people who have never seen the CSS.

Every model that appears on the public site has `published` and `order`, so
anything can be hidden or reordered from the admin without a deploy.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Published(models.QuerySet):
    def live(self):
        return self.filter(published=True)


class ContentBase(models.Model):
    published = models.BooleanField(default=True, help_text="Untick to hide this from the site.")
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers come first.")
    updated_at = models.DateTimeField(auto_now=True)

    objects = Published.as_manager()

    class Meta:
        abstract = True
        ordering = ["order", "id"]


def bullet_help(what):
    return f"One {what} per line. Blank lines are ignored."


class BulletsField(models.TextField):
    """Bullets are edited as plain lines, which is what people expect.

    Stored as text rather than JSON so the admin gives a normal textarea and
    nobody has to type brackets and quotes to add a bullet point.
    """

    def as_list(self, value):
        return [line.strip() for line in (value or "").splitlines() if line.strip()]


class SiteSettings(models.Model):
    """One row. The things that appear on every page."""

    community_name = models.CharField(max_length=80, default="KDU Developer Community")
    university = models.CharField(max_length=120, default="Kyungdong University")
    country = models.CharField(max_length=80, default="South Korea")
    founded = models.CharField(max_length=40, default="August 2026")

    footer_blurb = models.TextField(
        default="A student-run developer community based at Kyungdong University, South "
                "Korea, open to students there and to any other developer.",
        help_text="Shown in the footer of every page.",
    )

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return self.community_name

    def save(self, *args, **kwargs):
        # A singleton. Anything that tries to create a second row updates the
        # first one instead, including Model.objects.create(), which would
        # otherwise force an insert and hit the primary key constraint.
        self.pk = 1
        kwargs.pop("force_insert", None)
        self._state.adding = False
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("The site settings row cannot be deleted.")

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj



class SocialLink(ContentBase):
    """Somewhere the community exists other than this site.

    A model rather than a handful of URL fields on the settings row, so that
    adding a platform is something the leadership team can do in the admin
    instead of something that needs a migration and a deploy.

    Two groups, because they answer different questions. "Where we talk" is
    how a member reaches the community day to day; "Follow us" is where an
    outsider sees what it is doing. A platform can honestly be either, so the
    group is chosen per link rather than fixed per platform.
    """

    GROUP_CHAT = "chat"
    GROUP_SOCIAL = "social"
    GROUP_CHOICES = [
        (GROUP_CHAT, "Where we talk"),
        (GROUP_SOCIAL, "Follow us"),
    ]

    name = models.CharField(
        max_length=40,
        help_text="Shown as the link text. For example Facebook, LinkedIn, GitHub, "
                  "Instagram, X, Discord, WhatsApp.",
    )
    url = models.URLField(
        blank=True,
        default="",
        help_text="Leave blank to list the platform with a 'Soon' badge instead of a link.",
    )
    group = models.CharField(max_length=10, choices=GROUP_CHOICES, default=GROUP_SOCIAL)
    handle = models.CharField(
        max_length=80,
        blank=True,
        default="",
        help_text="Optional. The account name, if it is worth showing. For example @kdudev.",
    )

    class Meta(ContentBase.Meta):
        verbose_name = "social link"
        verbose_name_plural = "social links"

    def __str__(self):
        return self.name

    @property
    def is_live(self):
        return bool(self.url)


class Page(ContentBase):
    """A prose page: rules, terms, privacy, accessibility, contribute, start.

    The sections are separate rows so each one keeps its own heading, anchor
    and bullet list, which is what the contents list in the margin is built
    from.
    """

    class Layout(models.TextChoices):
        DOCUMENT = "document", "Document, with a contents list in the margin"
        PLAIN = "plain", "Plain, narrow column"

    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=120)
    eyebrow = models.CharField(max_length=120, blank=True, default="",
                               help_text="Small line above the title.")
    lead = models.TextField(help_text="The paragraph under the title. Also the meta description.")
    layout = models.CharField(max_length=12, choices=Layout.choices, default=Layout.DOCUMENT)

    show_version = models.BooleanField(default=False, help_text="Show the version and review date.")
    version = models.CharField(max_length=20, blank=True, default="Version 1")
    reviewed_on = models.DateField(null=True, blank=True)

    intro = models.TextField(blank=True, default="", help_text="Optional paragraph before the first section.")
    notice_title = models.CharField(max_length=120, blank=True, default="",
                                    help_text="Optional boxed note at the top. Leave blank for none.")
    notice_body = models.TextField(blank=True, default="")

    class Meta(ContentBase.Meta):
        verbose_name = "page"

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("content:page", args=[self.slug])


class PageSection(models.Model):
    page = models.ForeignKey(Page, related_name="sections", on_delete=models.CASCADE)
    anchor = models.SlugField(max_length=60, blank=True,
                              help_text="Used for the link in the contents list. Filled in from the heading if blank.")
    heading = models.CharField(max_length=160)
    body = models.TextField(blank=True, default="", help_text="One paragraph per blank-line-separated block.")
    bullets = BulletsField(blank=True, default="", help_text=bullet_help("bullet point"))
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.heading

    def save(self, *args, **kwargs):
        if not self.anchor:
            self.anchor = slugify(self.heading)[:60]
        super().save(*args, **kwargs)

    @property
    def paragraphs(self):
        return [block.strip() for block in self.body.split("\n\n") if block.strip()]

    @property
    def bullet_list(self):
        return BulletsField().as_list(self.bullets)


class Activity(ContentBase):
    """One of the things the community runs. Index entry and detail page."""

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    cadence = models.CharField(max_length=60, help_text='For example "Weekly" or "Once a term".')
    cadence_is_primary = models.BooleanField(
        default=False, help_text="Show the cadence tag in the darker style.")
    extra_tag = models.CharField(max_length=40, blank=True, default="",
                                 help_text='Optional second tag, e.g. "Member-run".')
    summary = models.TextField(help_text="Shown on the activities index and used as the meta description.")
    body = models.TextField(blank=True, default="",
                            help_text="Paragraphs for the index entry. One per blank-line-separated block.")
    index_bullets = BulletsField(blank=True, default="",
                                 help_text=bullet_help("bullet shown on the index page"))

    class Meta(ContentBase.Meta):
        verbose_name = "activity"
        verbose_name_plural = "activities"

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("content:activity", args=[self.slug])

    @property
    def paragraphs(self):
        return [block.strip() for block in self.body.split("\n\n") if block.strip()]

    @property
    def index_bullet_list(self):
        return BulletsField().as_list(self.index_bullets)


class ActivitySection(models.Model):
    """A heading-and-body block on an activity's own page."""

    activity = models.ForeignKey(Activity, related_name="sections", on_delete=models.CASCADE)
    heading = models.CharField(max_length=160)
    body = models.TextField(blank=True, default="")
    bullets = BulletsField(blank=True, default="", help_text=bullet_help("bullet point"))
    bullets_in_columns = models.BooleanField(default=False)
    note_title = models.CharField(max_length=120, blank=True, default="",
                                  help_text="Turns this section into a boxed note.")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.heading

    @property
    def paragraphs(self):
        return [block.strip() for block in self.body.split("\n\n") if block.strip()]

    @property
    def bullet_list(self):
        return BulletsField().as_list(self.bullets)


class HomeCard(ContentBase):
    """One of the four things on the home page."""

    class Icon(models.TextChoices):
        BOOK = "book", "Open book"
        BRACKETS = "brackets", "Code brackets"
        NETWORK = "network", "Connected people"
        SCREEN = "screen", "Screen"

    title = models.CharField(max_length=80)
    body = models.TextField()
    icon = models.CharField(max_length=12, choices=Icon.choices, default=Icon.BOOK)

    class Meta(ContentBase.Meta):
        verbose_name = "home page card"

    def __str__(self):
        return self.title


class Fact(ContentBase):
    """One cell of the at-a-glance strip on the home page."""

    label = models.CharField(max_length=40)
    value = models.CharField(max_length=60)

    class Meta(ContentBase.Meta):
        verbose_name = "home page fact"

    def __str__(self):
        return f"{self.label}: {self.value}"


class Value(ContentBase):
    """Something the community holds members to. Shown on the About page."""

    title = models.CharField(max_length=80)
    body = models.TextField()

    class Meta(ContentBase.Meta):
        verbose_name = "value"

    def __str__(self):
        return self.title


class ResponsibilityArea(ContentBase):
    """An area of work, described without naming a person."""

    name = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=120, blank=True, default="")
    bullets = BulletsField(help_text=bullet_help("responsibility"))

    class Meta(ContentBase.Meta):
        verbose_name = "area of responsibility"

    def __str__(self):
        return self.name

    @property
    def bullet_list(self):
        return BulletsField().as_list(self.bullets)


class JoinStep(ContentBase):
    """One step of the joining process."""

    title = models.CharField(max_length=80)
    body = models.TextField()

    class Meta(ContentBase.Meta):
        verbose_name = "joining step"

    def __str__(self):
        return self.title


class FaqEntry(ContentBase):
    question = models.CharField(max_length=160)
    anchor = models.SlugField(max_length=60, blank=True)
    answer = models.TextField(help_text="One paragraph per blank-line-separated block.")

    class Meta(ContentBase.Meta):
        verbose_name = "question"
        verbose_name_plural = "questions"

    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        if not self.anchor:
            self.anchor = slugify(self.question)[:60]
        super().save(*args, **kwargs)

    @property
    def paragraphs(self):
        return [block.strip() for block in self.answer.split("\n\n") if block.strip()]


class InterestArea(ContentBase):
    """One of the areas on the application form, explained."""

    name = models.CharField(max_length=80)
    subtitle = models.CharField(max_length=120, blank=True, default="")
    bullets = BulletsField(help_text=bullet_help("line"))
    on_application_form = models.BooleanField(
        default=True, help_text="Offer this as a tick box on the join form.")

    class Meta(ContentBase.Meta):
        verbose_name = "interest area"

    def __str__(self):
        return self.name

    @property
    def bullet_list(self):
        return BulletsField().as_list(self.bullets)


class ResourceGroup(ContentBase):
    heading = models.CharField(max_length=120)
    anchor = models.SlugField(max_length=60, blank=True)
    body = models.TextField(blank=True, default="")

    class Meta(ContentBase.Meta):
        verbose_name = "resource group"

    def __str__(self):
        return self.heading

    def save(self, *args, **kwargs):
        if not self.anchor:
            self.anchor = slugify(self.heading)[:60]
        super().save(*args, **kwargs)


class Resource(ContentBase):
    group = models.ForeignKey(ResourceGroup, related_name="links", on_delete=models.CASCADE)
    title = models.CharField(max_length=120)
    url = models.URLField()
    note = models.CharField(max_length=200, blank=True, default="",
                            help_text="Why it is worth someone's time.")

    class Meta(ContentBase.Meta):
        verbose_name = "resource"

    def __str__(self):
        return self.title
