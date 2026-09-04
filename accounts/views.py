"""Signing up, confirming an address, and a member's own page."""

import logging

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from applications.views import _rate_limited
from content.views import base_context

from .emails import read_token, send_welcome_email
from .forms import EmailLoginForm, ProfileForm, SignUpForm
from .models import Member

log = logging.getLogger(__name__)


def _context(request, title, description, **extra):
    context = base_context(request, title, description, nav="account")
    context.update(extra)
    return context


@require_http_methods(["GET", "POST"])
def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    form = SignUpForm(request.POST or None)

    if request.method == "POST":
        # Same limiter as the join form, for the same reason: a sign-up form
        # is a free way to send mail to any address somebody types.
        if _rate_limited(request, scope="signup"):
            messages.error(request, "Too many attempts from this connection. "
                                    "Please wait a few minutes and try again.")
        elif form.is_valid():
            user = form.save()
            member = user.member
            sent = send_welcome_email(member, request)
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
        request,
        "Create an account",
        "Create an account for the KDU Developer Community to keep your details "
        "up to date and follow your application.",
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

    member.mark_verified()
    return render(request, "accounts/verify.html", _context(
        request, "Email address confirmed",
        "Your email address is confirmed.",
        ok=True, member=member,
    ))


@login_required
@require_http_methods(["POST"])
def resend_verification(request):
    member = getattr(request.user, "member", None)
    if member is None:
        return redirect("accounts:dashboard")

    if member.is_verified:
        messages.info(request, "That address is already confirmed.")
    elif _rate_limited(request, scope="verify"):
        messages.error(request, "Too many attempts. Please wait a few minutes.")
    elif send_welcome_email(member, request):
        messages.success(request, f"A new link is on its way to {member.email}.")
    else:
        messages.error(request, "We could not send it just now. Please try again shortly.")
    return redirect("accounts:dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def dashboard(request):
    member = getattr(request.user, "member", None)
    if member is None:
        # A staff account created with createsuperuser has no member row. It
        # belongs in the admin, not here.
        return redirect("admin:index")

    form = ProfileForm(request.POST or None, instance=member)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.interests = list(form.cleaned_data.get("interests") or [])
        updated.save()
        # Keep the two copies of the name in step, since the admin shows one
        # and the site shows the other.
        request.user.first_name = updated.display_name[:150]
        request.user.save(update_fields=["first_name"])
        messages.success(request, "Your details are saved.")
        return redirect("accounts:dashboard")

    return render(request, "accounts/dashboard.html", _context(
        request, "Your account",
        "Your details, and where your application stands.",
        member=member, form=form, applications=member.applications(),
    ))


class SignIn(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(base_context(
            self.request, "Sign in",
            "Sign in to your KDU Developer Community account.", nav="account"))
        return context


class SignOut(LogoutView):
    next_page = reverse_lazy("content:home")
