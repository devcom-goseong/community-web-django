"""Accounts, and the member pages: the directory and profiles.

Every page that shows members to other people asks accounts.access who may see
what, and answers a refusal with a page that says why and what to do next.
Pages about a person set noindex and private caching whatever they show,
because a search engine or a shared cache is the last place a member's details
should end up.
"""

import logging
from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from applications.models import Application
from config.ratelimit import rate_limited
from content.context_processors import link_views
from content.models import SocialLink
from content.views import base_context

from .access import access_state, can_see_members_area, is_staff, member_of
from .emails import read_token, send_approval_email, send_welcome_email
from .forms import (
    CloseAccountForm,
    DirectoryFilterForm,
    EmailLoginForm,
    ProfileForm,
    ProjectFormSet,
    SignUpForm,
)
from .models import Member
from .services import approve_if_already_accepted

log = logging.getLogger(__name__)

DIRECTORY_PAGE_SIZE = 24


def personal(view):
    """For pages about a person: never cached, never indexed."""
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response
    return never_cache(wrapped)


def _context(request, title, description, nav="account", **extra):
    context = base_context(request, title, description, nav=nav)
    context["noindex"] = True
    context.update(extra)
    return context


def _restricted(request, kind, status):
    context = _context(
        request, "Not available",
        "This page is only for members of the community.", nav="members",
        kind=kind, state=access_state(request.user), next=request.get_full_path())
    return render(request, "members/restricted.html", context, status=status)


# --- signing up and in ------------------------------------------------------

@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = SignUpForm(request.POST or None)

    if request.method == "POST":
        # A sign-up form is a free way to send mail to any address somebody
        # types, so it is rate limited like the join form.
        if rate_limited(request, scope="signup"):
            messages.error(request, "Too many attempts from this connection. "
                                    "Please wait a few minutes and try again.")
        elif form.is_valid():
            user = form.save()
            sent = send_welcome_email(user.member, request)
            login(request, user, backend="accounts.backends.EmailBackend")
            if sent:
                messages.success(
                    request,
                    f"Your account is ready. We have sent a link to {user.email} — "
                    "open it to confirm the address.")
            else:
                messages.warning(
                    request,
                    "Your account is ready, but we could not send the confirmation "
                    "email just now. You can ask for another one below.")
            return redirect("accounts:dashboard")

    return render(request, "accounts/signup.html", _context(
        request, "Create an account",
        "Create an account for the KDU Developer Community.",
        form=form,
    ))


@require_http_methods(["GET"])
def verify(request, token):
    """Confirm an address from the signed link in the welcome email."""
    payload = read_token(token)
    member = None
    if payload:
        member = Member.objects.filter(user_id=payload.get("uid")).select_related("user").first()
        # The address is checked against the account, so a link issued for an
        # address that has since changed does not silently verify the new one.
        if member and member.user.email.lower() != str(payload.get("email", "")).lower():
            member = None

    if member is None:
        return render(request, "accounts/verify.html", _context(
            request, "That link did not work",
            "The confirmation link is expired or is not valid.",
            ok=False,
        ), status=400)

    newly_confirmed = member.mark_verified()
    approved = approve_if_already_accepted(member)
    if newly_confirmed and not approved and member.status == Member.Status.ACTIVE:
        # Approved by the leadership team before they had confirmed their
        # address. The approval email waited for confirmation; send it now.
        send_approval_email(member, request)
        approved = True
    return render(request, "accounts/verify.html", _context(
        request, "Email address confirmed",
        "Your email address is confirmed.",
        ok=True, member=member, approved=approved,
    ))


@login_required
@require_http_methods(["POST"])
def resend_verification(request):
    member = member_of(request.user)
    if member is None:
        return redirect("accounts:dashboard")

    if member.is_verified:
        messages.info(request, "That address is already confirmed.")
    elif rate_limited(request, scope="verify"):
        messages.error(request, "Too many attempts. Please wait a few minutes.")
    elif send_welcome_email(member, request):
        messages.success(request, f"A new link is on its way to {member.email}.")
    else:
        messages.error(request, "We could not send it just now. Please try again shortly.")
    return redirect("accounts:dashboard")


class SignIn(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # LoginView adds Django's own `site` (a RequestSite with no community
        # name), which would shadow the site settings every template reads.
        context.pop("site", None)
        context.pop("site_name", None)
        context.update(_context(
            self.request, "Sign in", "Sign in to your KDU Developer Community account."))
        return context


class SignOut(LogoutView):
    next_page = reverse_lazy("content:home")


# --- a member's own pages ---------------------------------------------------

@login_required
@personal
@require_http_methods(["GET"])
def dashboard(request):
    member = member_of(request.user)
    if member is None:
        # A staff account made with createsuperuser has no member row. It
        # belongs in the admin, not here. Anyone else without one has lost it
        # through an admin mistake, and the admin would only refuse them.
        if is_staff(request.user):
            return redirect("admin:index")
        messages.error(request, "This account has no member details. Please contact the "
                                "leadership team.")
        return redirect("content:home")

    from events.models import Registration

    now = timezone.now()
    upcoming = list(
        Registration.objects.filter(
            member=member, event__ends_at__gte=now,
            status__in=[Registration.Status.GOING, Registration.Status.WAITLIST])
        .select_related("event").order_by("event__starts_at"))

    invite_links = []
    if can_see_members_area(request.user):
        invite_links = [link for link in link_views(SocialLink.GROUP_CHAT, request.user)
                        if link.is_live]

    return render(request, "accounts/dashboard.html", _context(
        request, "Your account", "Your membership, your events and your profile.",
        member=member,
        state=access_state(request.user),
        invite_links=invite_links,
        upcoming=upcoming,
        # Applications are matched by email address, so until the address is
        # confirmed they could belong to someone else: anyone can sign up with
        # another person's address, and must not learn whether that person
        # applied or how it went.
        applications=member.applications() if member.is_verified else [],
    ))


@login_required
@personal
@require_http_methods(["GET", "POST"])
def profile_edit(request):
    member = member_of(request.user)
    if member is None:
        return redirect("admin:index")

    form = ProfileForm(request.POST or None, instance=member)
    projects = ProjectFormSet(request.POST or None, instance=member, prefix="projects")

    if request.method == "POST" and form.is_valid() and projects.is_valid():
        with transaction.atomic():
            member = form.save()
            saved = projects.save(commit=False)
            for obj in projects.deleted_objects:
                obj.delete()
            for index, obj in enumerate(saved):
                obj.member = member
                if obj.pk is None:
                    # New projects go to the end of the list, not the top.
                    obj.order = 10_000 + index
                obj.save()
            for position, project in enumerate(member.projects.order_by("order", "pk")):
                if project.order != position:
                    project.order = position
                    project.save(update_fields=["order"])
            # Keep the admin's copy of the name in step with the site's.
            request.user.first_name = member.display_name[:150]
            request.user.save(update_fields=["first_name"])
        messages.success(request, "Your profile is saved.")
        return redirect("accounts:profile_edit")

    return render(request, "accounts/profile_edit.html", _context(
        request, "Edit your profile", "Your name, your profile address, who can see it, "
                                      "and what it shows.",
        member=member, form=form, projects=projects,
    ))


@login_required
@personal
@require_http_methods(["GET", "POST"])
def close_account(request):
    user = request.user
    if is_staff(user) or user.is_superuser:
        # A leadership account closing itself from here could lock the
        # community out of its own admin. Another admin does it from there.
        messages.error(request, "Leadership team accounts are closed from the admin, by "
                                "another member of the team.")
        return redirect("accounts:dashboard")

    form = CloseAccountForm(user, request.POST or None)
    if request.method == "POST":
        if rate_limited(request, scope="close-account"):
            messages.error(request, "Too many attempts. Please wait a few minutes.")
        elif form.is_valid():
            email = user.email
            with transaction.atomic():
                if form.cleaned_data["delete_applications"]:
                    Application.objects.filter(email__iexact=email).delete()
                # Deleting the user deletes the member, their projects and
                # their registrations. Places they held are offered to the
                # waiting list first, by a signal in the events app.
                logout(request)
                user.delete()
            log.info("a member closed their account")
            messages.success(request, "Your account is closed, and everything on it has been "
                                      "deleted. Thank you for being part of the community.")
            return redirect("content:home")

    return render(request, "accounts/close.html", _context(
        request, "Close your account", "Delete your account and everything on it.",
        form=form,
    ))


# --- the members directory and profiles -------------------------------------

@personal
def directory(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={request.path}")
    if not can_see_members_area(request.user):
        return _restricted(request, "directory", status=403)

    filters = DirectoryFilterForm(request.GET or None)
    query = interest = ""
    if filters.is_valid():
        query = filters.cleaned_data["q"].strip()
        interest = filters.cleaned_data["interest"]

    members = (Member.objects
               .filter(status=Member.Status.ACTIVE, email_verified_at__isnull=False,
                       user__is_active=True,
                       profile_visibility__in=[Member.Visibility.MEMBERS,
                                               Member.Visibility.PUBLIC])
               .select_related("user")
               .order_by(Lower("display_name"), "pk"))
    if query:
        members = members.filter(Q(display_name__icontains=query)
                                 | Q(handle__icontains=query)
                                 | Q(bio__icontains=query))
    if interest:
        # A JSON "contains" lookup is not available on SQLite, which is what
        # runs locally, so filter in Python there. The directory is small
        # enough for that to be fine, and PostgreSQL does it in the database.
        if connection.features.supports_json_field_contains:
            members = members.filter(interests__contains=[interest])
        else:
            members = [m for m in members if interest in (m.interests or [])]

    page = Paginator(members, DIRECTORY_PAGE_SIZE).get_page(request.GET.get("page"))
    kept = request.GET.copy()
    kept.pop("page", None)

    return render(request, "members/directory.html", _context(
        request, "Members", "Find people in the community to learn and build with.",
        nav="members",
        filters=filters, page=page, query=query, interest=interest,
        querystring=kept.urlencode(),
    ))


@personal
def profile(request, handle):
    if handle != handle.lower():
        return redirect("members:profile", handle=handle.lower(), permanent=True)

    member = Member.objects.select_related("user").filter(handle=handle).first()
    if member is None or not member.profile_visible_to(request.user):
        # Identical for "does not exist" and "not for you", so the page cannot
        # be used to find out which handles belong to real people.
        return _restricted(request, "profile", status=404)

    from events.models import Event, Registration

    attended = Registration.objects.filter(
        member=member, attended=True, event__status=Event.Status.PUBLISHED)
    if not can_see_members_area(request.user):
        # A profile set to "anyone with the link" is readable by strangers,
        # and the title of a members-only event is itself members-only.
        attended = attended.filter(event__visibility=Event.Visibility.PUBLIC)
    attended = list(attended.select_related("event__activity").order_by("-event__starts_at"))

    viewer = member_of(request.user)
    return render(request, "members/profile.html", _context(
        request, member.display_name, f"{member.display_name} in the KDU Developer Community.",
        nav="members",
        member=member,
        projects=list(member.projects.all()),
        attended=attended,
        is_owner=bool(viewer and viewer.pk == member.pk),
    ))
