"""The page a presenter opens from the link an admin sent them.

No account is needed: the link itself is the permission, and it works once.
"""

import base64
import logging
import mimetypes

from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.access import is_staff
from config.ratelimit import rate_limited
from content.views import base_context

from . import emails, services
from .forms import PresenterForm
from .models import TalkPoster

log = logging.getLogger(__name__)


def _context(request, title, **extra):
    context = base_context(request, title, "Send the details of your talk for its poster.")
    context["noindex"] = True
    context.update(extra)
    return context


def _closed(request, talk, status):
    response = render(request, "posters/link_closed.html",
                      _context(request, "This link no longer works", talk=talk), status=status)
    response["X-Robots-Tag"] = "noindex"
    return response


@never_cache
def present(request, token):
    talk = TalkPoster.objects.filter(token=token).first()
    if talk is None:
        return _closed(request, None, 404)
    if not talk.link_is_open():
        return _closed(request, talk, 410)

    posted = request.method == "POST"
    form = PresenterForm(request.POST if posted else None, request.FILES if posted else None,
                         instance=talk)
    if posted:
        # Generous, because a presenter may need a few goes to get the photo right.
        if rate_limited(request, scope="present", limit=20):
            form.add_error(None, "Too many tries from this connection. Please wait a few "
                                 "minutes and send it again.")
        elif form.is_valid():
            return _submit(request, form)

    response = render(request, "posters/present.html", _context(
        request, "Your talk", form=form, talk=talk,
        start=timezone.localtime(talk.starts_at), end=timezone.localtime(talk.ends_at)))
    response["X-Robots-Tag"] = "noindex"
    return response


def _submit(request, form):
    with transaction.atomic():
        locked = TalkPoster.objects.select_for_update().get(pk=form.instance.pk)
        if not locked.link_is_open():
            # Sent twice, from two tabs: the first one wins.
            return _closed(request, locked, 410)
        talk = form.save(commit=False)
        if "photo" in form.changed_data:
            # Not the file as sent: store_photo keeps a cleaned copy instead,
            # and removes the photo from any earlier go.
            talk.photo = locked.photo.name
            services.store_photo(talk, form.cleaned_data["photo"])
        services.draw(talk)
        talk.status = TalkPoster.Status.SUBMITTED
        talk.submitted_at = timezone.now()
        talk.save()
        transaction.on_commit(lambda: emails.send_submitted(talk.pk))

    with talk.poster.open("rb") as poster:
        preview = base64.b64encode(poster.read()).decode("ascii")
    response = render(request, "posters/present_done.html",
                      _context(request, "Thank you", talk=talk, preview=preview))
    response["X-Robots-Tag"] = "noindex"
    return response


def staff_file(request, path):
    """An uploaded file, for the leadership team only.

    The admin links photos and posters by their MEDIA_URL; this answers those
    links. Anyone else gets a 404, the same as for a file that does not exist.
    """
    if not is_staff(request.user):
        raise Http404("Not found")
    try:
        if not default_storage.exists(path):
            raise Http404("Not found")
        handle = default_storage.open(path, "rb")
    except SuspiciousFileOperation as exc:
        raise Http404("Not found") from exc
    kind = mimetypes.guess_type(path)[0] or "application/octet-stream"
    response = FileResponse(handle, content_type=kind)
    response["Cache-Control"] = "private, max-age=600"
    return response
