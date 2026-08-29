from django.db import models
from django.utils import timezone


class Application(models.Model):
    """One submission of the join / contact form.

    Deliberately does not store an IP address. The published privacy notice
    says the submitter's IP is held only in memory for rate limiting and is
    never stored, and that statement has to stay true. The rate limiter keeps
    a hashed counter in the cache instead.
    """

    class Intent(models.TextChoices):
        JOIN = "join", "Membership application"
        QUESTION = "question", "Question"

    class Student(models.TextChoices):
        YES = "yes", "Yes"
        NO = "no", "No"
        SOON = "soon", "Starting soon"
        UNKNOWN = "", "Not answered"

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWING = "reviewing", "Being reviewed"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        SPAM = "spam", "Spam"

    intent = models.CharField(max_length=16, choices=Intent.choices, default=Intent.JOIN)
    name = models.CharField(max_length=120)
    email = models.EmailField(max_length=160)
    student = models.CharField(max_length=8, choices=Student.choices, blank=True, default="")
    student_id = models.CharField("student ID", max_length=40, blank=True, default="")
    interests = models.JSONField(default=list, blank=True)
    message = models.TextField(max_length=2000, blank=True, default="")

    # What they agreed to, and when. Kept because it is the record that the
    # rules, terms and privacy notice were accepted.
    consented_to_contact = models.BooleanField(default=False)
    accepted_documents = models.BooleanField(
        default=False, help_text="Accepted the community rules, terms and privacy notice."
    )
    accepted_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW, db_index=True)
    review_notes = models.TextField(blank=True, default="", help_text="Internal. Never emailed.")
    reviewed_by = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_applications"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    confirmation_sent = models.BooleanField(default=False)
    notification_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "application"
        verbose_name_plural = "applications"
        indexes = [models.Index(fields=["intent", "status"])]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def is_question(self):
        return self.intent == self.Intent.QUESTION

    def mark_reviewed(self, user, status):
        self.status = status
        self.reviewed_by = user
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_by", "reviewed_at"])
