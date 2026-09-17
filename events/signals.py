"""Free a deleted member's places before their registrations disappear.

When an account is deleted — by the member closing it, or from the admin — its
registrations go with it in the cascade. Nothing would then tell the next person
on the waiting list that a place had opened. This runs first and does exactly
what cancelling would have done.
"""

from django.db.models.signals import pre_delete
from django.dispatch import receiver

from accounts.models import Member

from .services import release_places


@receiver(pre_delete, sender=Member, dispatch_uid="events.release_places_on_member_delete")
def release_places_before_member_is_deleted(sender, instance, **kwargs):
    release_places(instance)
