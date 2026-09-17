"""Give every existing member a handle, and an approval date if they are a member.

Its own migration so the rows are updated in a transaction of their own, before
the next migration makes the handle unique. See 0002 for why that matters.

Profiles start hidden, which is the model's default: nobody who signed up
before profiles existed is listed anywhere until they choose to be.
"""

from django.db import migrations

from accounts.validators import generate_handle


def fill(apps, schema_editor):
    Member = apps.get_model("accounts", "Member")
    used = set()

    for member in Member.objects.order_by("pk"):
        if member.handle:
            used.add(member.handle.lower())
            continue
        member.handle = generate_handle(member.display_name, lambda c: c.lower() in used)
        used.add(member.handle)
        fields = ["handle"]
        # The real approval time was never recorded. The account's creation
        # date is the closest honest stand-in: approval cannot have come before it.
        if member.status == "active" and member.approved_at is None:
            member.approved_at = member.created_at
            fields.append("approved_at")
        member.save(update_fields=fields)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_member_profiles"),
    ]

    operations = [
        migrations.RunPython(fill, migrations.RunPython.noop),
    ]
