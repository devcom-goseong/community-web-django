"""A deleted talk poster takes its photo and its poster file with it."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import TalkPoster


@receiver(post_delete, sender=TalkPoster, dispatch_uid="posters.delete_files")
def delete_files(sender, instance, **kwargs):
    for field in (instance.photo, instance.poster):
        if field.name:
            storage, name = field.storage, field.name
            transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
