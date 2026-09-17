"""Invite links become members-only.

The column is added switched on for every row, then switched off again for the
"Follow us" links, which are public pages meant to be seen. What is left on is
the "Where we talk" group: the Discord and WhatsApp invites, which until now
were printed on every page for anyone to use.

The schema change comes before the data change here, which is the safe order on
PostgreSQL: it is altering a table after updating its rows in the same
transaction that fails, not the other way round.
"""

from django.db import migrations, models


def open_the_public_links(apps, schema_editor):
    SocialLink = apps.get_model("content", "SocialLink")
    SocialLink.objects.filter(group="social").update(members_only=False)


def close_everything(apps, schema_editor):
    SocialLink = apps.get_model("content", "SocialLink")
    SocialLink.objects.update(members_only=True)


class Migration(migrations.Migration):

    dependencies = [
        ("content", "0002_social_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="sociallink",
            name="members_only",
            field=models.BooleanField(
                default=True,
                help_text="Only show the address to approved members who are signed in. "
                          "Everyone else sees the platform's name with a 'Members' badge. Use "
                          "this for invite links to Discord, WhatsApp and similar; untick it "
                          "for public pages people can follow. If an invite link is ever "
                          "shared outside the community, make a new one on the platform, "
                          "revoke the old one there, and paste the new one here.",
            ),
        ),
        migrations.RunPython(open_the_public_links, close_everything),
    ]
