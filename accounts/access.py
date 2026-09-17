"""Who may see what. One place for the rules.

Every page that shows something to members asks these functions rather than
working it out itself. A page written next month cannot then quietly decide
that "signed in" means "member", which is the mistake that would put the
community's invite links or its members' profiles in front of a stranger.

The levels, from least to most:

  anonymous         not signed in
  signed in         has an account, but the address may not be confirmed
  confirmed         signed in, and has opened the link in the welcome email
  approved member   confirmed, and approved by the leadership team
  staff             the leadership team, who can see everything
"""

from django.core.exceptions import ObjectDoesNotExist


def member_of(user):
    """The Member row for this user, or None.

    Staff accounts made with createsuperuser have no Member row, and anonymous
    users have no row at all, so callers must not assume one exists.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    try:
        return user.member
    except ObjectDoesNotExist:
        return None


def is_approved_member(user):
    member = member_of(user)
    return bool(member and user.is_active and member.is_active_member)


def is_staff(user):
    return bool(getattr(user, "is_authenticated", False) and user.is_active and user.is_staff)


def can_see_members_area(user):
    """The members directory, profiles set to 'members', and invite links."""
    return is_staff(user) or is_approved_member(user)


def access_state(user):
    """A single word describing where someone is, for pages that explain it.

    The pages that refuse someone say *why* and what to do next, because
    "you do not have permission" tells a person who has just signed up nothing
    about the fact that they are one email click away.
    """
    if not getattr(user, "is_authenticated", False):
        return "anonymous"
    if is_staff(user):
        return "staff"
    member = member_of(user)
    if member is None or not user.is_active:
        return "no-member"
    if not member.is_verified:
        return "unconfirmed"
    if member.status == member.Status.PENDING:
        return "pending"
    if member.status != member.Status.ACTIVE:
        return "inactive"
    return "member"
