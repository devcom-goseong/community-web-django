"""Talk posters in the admin: make a link, check what comes back, put it on an event.

The flow, from the admin's side:

  1. Add a talk poster. Pick the event if it exists, or set the date, time and
     place. Saving shows the link, with a button to copy it.
  2. Send the link to the presenter, however you usually reach them.
  3. When they send the form, the team inbox gets the poster. It is not on the
     site yet. Open it here, fix any text if needed (the poster is drawn again
     on save), then "Approve and put it on an event".
"""

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from events.models import Event

from . import services
from .forms import ApproveForm, TalkPosterAdminForm
from .models import LINK_DAYS, TalkPoster

# Changing any of these changes what the poster shows, so it is drawn again.
DRAWN_FROM = {"label", "starts_at", "ends_at", "platform", "place", "place_detail", "title",
              "summary", "about", "speaker_name", "speaker_tag", "photo"}


def _when(moment):
    local = timezone.localtime(moment)
    return f"{local:%a} {local.day} {local:%b} {local:%H:%M}"


@admin.register(TalkPoster)
class TalkPosterAdmin(admin.ModelAdmin):
    form = TalkPosterAdminForm
    list_display = ("__str__", "starts_local", "status", "link_state", "event")
    list_filter = ("status",)
    search_fields = ("title", "speaker_name", "summary")
    list_select_related = ("event",)
    actions = ("new_link", "take_off_event")
    radio_fields = {"platform": admin.HORIZONTAL}
    readonly_fields = ("presenter_link", "status", "poster_preview", "submitted_at",
                       "approved_at", "approved_by", "created_by", "created_at")

    def get_fieldsets(self, request, obj=None):
        when = ("When and where", {
            "fields": ("event", "label", ("starts_at", "ends_at"), "platform", "place",
                       "place_detail"),
            "description": "You set these. The presenter sees them but cannot change them. "
                           "Times are in Korean time (KST). Pick an event and its date and "
                           "time are filled in for you.",
        })
        if obj is None:
            return (when, ("The link", {
                "fields": ("link_expires_at",),
                "description": f"When you save, the link appears on the next page, ready to "
                               f"copy and send. It works for {LINK_DAYS} days, or until the "
                               f"presenter sends the form.",
            }))
        return (
            ("The link for the presenter", {"fields": ("presenter_link", "link_expires_at",
                                                       "status")}),
            ("The poster", {"fields": ("poster_preview",)}),
            ("From the presenter", {
                "fields": ("title", "summary", "about", "speaker_name", "speaker_tag", "photo",
                           "submitted_at"),
                "description": "You can correct anything here. The poster is drawn again "
                               "when you save.",
            }),
            when,
            ("Record", {"fields": ("approved_at", "approved_by", "created_by", "created_at"),
                        "classes": ("collapse",)}),
        )

    # --- what the pages show -------------------------------------------------

    @admin.display(description="starts", ordering="starts_at")
    def starts_local(self, obj):
        return _when(obj.starts_at)

    @admin.display(description="link")
    def link_state(self, obj):
        if obj.link_is_open():
            return f"Open until {_when(obj.link_expires_at)}"
        if obj.status != TalkPoster.Status.WAITING:
            return "Used"
        return "Expired"

    @admin.display(description="Link")
    def presenter_link(self, obj):
        if obj.link_is_open():
            url = f"{settings.APP_URL}{obj.get_absolute_url()}"
            return format_html(
                '<input type="text" value="{}" readonly style="width:100%;max-width:44em" '
                'onclick="this.select()"> '
                '<button type="button" class="button" onclick="navigator.clipboard.writeText('
                "this.previousElementSibling.value);this.textContent='Copied'\">Copy</button>"
                '<div class="help">Send this to the presenter. It works until {}, or until '
                "they send the form.</div>", url, _when(obj.link_expires_at))
        if obj.status != TalkPoster.Status.WAITING:
            sent = _when(obj.submitted_at) if obj.submitted_at else "an earlier date"
            return format_html(
                "Used: the presenter sent the form on {}. To let them change it, choose "
                "<strong>Give the presenter a new link</strong> from the list of talk posters.",
                sent)
        return format_html(
            "Expired on {} without being used. Choose <strong>Give the presenter a new "
            "link</strong> from the list of talk posters to send another.",
            _when(obj.link_expires_at))

    @admin.display(description="Poster")
    def poster_preview(self, obj):
        if not obj.poster:
            return "Drawn when the presenter sends the form."
        url = f"{obj.poster.url}?v={int(obj.updated_at.timestamp())}"
        approve = reverse("admin:posters_talkposter_approve", args=[obj.pk])
        if obj.status == TalkPoster.Status.APPROVED and obj.event:
            where = format_html(
                'On <a href="{}">{}</a>. <a class="button" href="{}">Move it to another '
                "event</a>", obj.event.get_absolute_url(), obj.event, approve)
        else:
            where = format_html(
                'Not on the site yet. <a class="button default" href="{}" style="padding:8px '
                '14px">Approve and put it on an event</a>', approve)
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" alt="The poster" style="width:340px;'
            'border:1px solid #dfe2e7;border-radius:8px"></a><p style="margin-top:12px">{}</p>',
            url, url, where)

    # --- saving --------------------------------------------------------------

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        if "photo" in form.changed_data and form.cleaned_data.get("photo"):
            previous = form.initial.get("photo")
            obj.photo = previous.name if previous else ""
            services.store_photo(obj, form.cleaned_data["photo"])
        if change and obj.is_filled_in and (DRAWN_FROM & set(form.changed_data) or not obj.poster):
            services.draw(obj)
        super().save_model(request, obj, form, change)

    def response_add(self, request, obj, post_url_continue=None):
        self.message_user(
            request, "The link is made. Copy it below and send it to the presenter.",
            messages.SUCCESS)
        return redirect("admin:posters_talkposter_change", obj.pk)

    # --- approving -----------------------------------------------------------

    def get_urls(self):
        return [
            path("<int:pk>/approve/", self.admin_site.admin_view(self.approve_view),
                 name="posters_talkposter_approve"),
        ] + super().get_urls()

    def approve_view(self, request, pk):
        talk = get_object_or_404(TalkPoster, pk=pk)
        if not self.has_change_permission(request, talk):
            raise PermissionDenied
        back = reverse("admin:posters_talkposter_change", args=[talk.pk])
        if not talk.poster or talk.status == TalkPoster.Status.WAITING:
            self.message_user(request, "There is nothing to approve yet: the presenter has not "
                                       "sent the form.", messages.WARNING)
            return redirect(back)

        form = ApproveForm(request.POST or None, talk=talk)
        if request.method == "POST" and form.is_valid():
            if form.cleaned_data["choice"] == ApproveForm.CREATE:
                try:
                    event = services.create_event(
                        talk, request.user, form.cleaned_data["status"] or Event.Status.DRAFT,
                        form.cleaned_data["online_url"])
                except ValidationError as error:
                    form.add_error(None, error)
                    event = None
                if event:
                    services.approve(talk, request.user, event)
                    self.message_user(request, format_html(
                        'Approved, and the event “{}” is made. Check its details below{}.',
                        event.title,
                        " and publish it when it is ready" if event.status == Event.Status.DRAFT
                        else ""), messages.SUCCESS)
                    return redirect("admin:events_event_change", event.pk)
            else:
                event = form.cleaned_data["event"]
                services.approve(talk, request.user, event)
                if not event.presenter:
                    event.presenter = talk.speaker_name
                    event.save(update_fields=["presenter", "updated_at"])
                self.message_user(request, format_html(
                    'Approved. The poster is on <a href="{}">{}</a>.',
                    event.get_absolute_url(), event.title), messages.SUCCESS)
                if (event.starts_at, event.ends_at) != (talk.starts_at, talk.ends_at):
                    self.message_user(request, (
                        f"Note: the event is on {_when(event.starts_at)}, but the poster says "
                        f"{_when(talk.starts_at)}. Change one of them so they agree."),
                        messages.WARNING)
                return redirect(back)

        return render(request, "admin/posters/talkposter/approve.html", {
            **self.admin_site.each_context(request),
            "title": "Approve the poster",
            "opts": self.model._meta,
            "original": talk,
            "talk": talk,
            "form": form,
            "poster_url": f"{talk.poster.url}?v={int(talk.updated_at.timestamp())}",
        })

    # --- actions -------------------------------------------------------------

    @admin.action(description="Give the presenter a new link")
    def new_link(self, request, queryset):
        talks = list(queryset)
        for talk in talks:
            talk.give_new_link()
            talk.save()
        if len(talks) == 1:
            self.message_user(request, "A new link is made. Copy it below and send it. What "
                                       "they sent before is filled in for them.",
                              messages.SUCCESS)
            return redirect("admin:posters_talkposter_change", talks[0].pk)
        self.message_user(request, f"{len(talks)} new links made. Open each poster to copy "
                                   f"its link.", messages.SUCCESS)
        return None

    @admin.action(description="Take the poster off its event page")
    def take_off_event(self, request, queryset):
        updated = queryset.filter(status=TalkPoster.Status.APPROVED).update(
            status=TalkPoster.Status.SUBMITTED, approved_at=None, approved_by=None)
        self.message_user(request, f"{updated} taken off. They stay here to approve again.",
                          messages.SUCCESS)
