"""Changing a member's status, and everything that has to happen when it changes.

A status is not just a label. Approving someone should tell them; pausing or
removing someone should give up the event places they were holding so the
waiting list moves; removing someone should take their profile down. If the
admin changed the status column directly, all of that would be skipped, so
every change goes through change_status.
"""

import logging

from django.db import transaction
from django.db.models.functions import Lower
from django.utils import timezone

from .models import Member

log = logging.getLogger(__name__)


def change_status(member, new_status):
    """Set a member's status and apply its consequences. Returns True if it changed."""
    old_status = member.status
    if old_status == new_status:
        return False

    fields = ["status", "updated_at"]
    member.status = new_status
    if new_status == Member.Status.ACTIVE and member.approved_at is None:
        member.approved_at = timezone.now()
        fields.append("approved_at")
    if new_status == Member.Status.REMOVED and member.profile_visibility != Member.Visibility.HIDDEN:
        # A removed member's profile is already invisible to everyone else, but
        # setting it back to hidden means it stays down if they are reinstated,
        # until they choose to show it again.
        member.profile_visibility = Member.Visibility.HIDDEN
        fields.append("profile_visibility")

    with transaction.atomic():
        member.save(update_fields=fields)

        from events.services import release_places

        if new_status in {Member.Status.PAUSED, Member.Status.REMOVED}:
            release_places(member)
        elif old_status == Member.Status.ACTIVE:
            # Back to awaiting review: they keep places at events open to any
            # confirmed account, but not at members-only ones.
            release_places(member, only_members_events=True)

        if new_status == Member.Status.ACTIVE and member.is_verified:
            member_id = member.pk
            transaction.on_commit(lambda: _send_approval(member_id))
    return True


def _send_approval(member_id):
    from .emails import send_approval_email

    member = Member.objects.select_related("user").filter(pk=member_id).first()
    if member is not None and member.is_active_member:
        send_approval_email(member)


def approve_if_already_accepted(member):
    """Approve a member whose application was already accepted.

    Someone can apply through the join form, be accepted, and only create an
    account afterwards. Asking the leadership team to approve the same person a
    second time would be busywork, so the account is approved as soon as its
    address is confirmed. Only after confirmation: until then, anyone could sign
    up with the address of someone who was accepted and inherit their approval.
    """
    if not member.is_verified or member.status != Member.Status.PENDING:
        return False
    from applications.models import Application

    accepted = Application.objects.filter(
        email__iexact=member.user.email,
        intent=Application.Intent.JOIN,
        status=Application.Status.ACCEPTED,
    ).exists()
    if accepted:
        change_status(member, Member.Status.ACTIVE)
    return accepted


def approve_accounts_for_applications(applications):
    """The other direction: accepting an application approves a matching account.

    Only accounts whose address is confirmed are approved, for the same reason
    as above. An unconfirmed one is approved later, by approve_if_already_accepted,
    when its owner opens the confirmation link.
    """
    emails = {a.email.lower() for a in applications if a.intent == a.Intent.JOIN}
    if not emails:
        return 0
    approved = 0
    candidates = (Member.objects.select_related("user")
                  .annotate(email_lower=Lower("user__email"))
                  .filter(email_lower__in=emails, status=Member.Status.PENDING,
                          email_verified_at__isnull=False))
    for member in candidates:
        if change_status(member, Member.Status.ACTIVE):
            approved += 1
    return approved
