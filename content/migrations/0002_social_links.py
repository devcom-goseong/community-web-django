"""Move the platform links off the settings row into their own model.

The four URL fields could only ever hold four platforms, and adding a fifth
meant a migration and a deploy. As rows they are something the leadership team
can manage in the admin.

Anything already filled in is carried across, so nothing has to be re-entered.
"""

from django.db import migrations, models

# The four that used to be fields, with the group each belongs in and the
# order they should appear in. The five the community asked for beyond these
# are seeded by `manage.py seed_content`, not here, because a migration should
# only move data that already exists.
CARRIED_OVER = [
    ("discord_url", "Discord", "chat", 10),
    ("whatsapp_url", "WhatsApp", "chat", 20),
    ("github_url", "GitHub", "social", 30),
    ("instagram_url", "Instagram", "social", 40),
]


def carry_links_over(apps, schema_editor):
    SiteSettings = apps.get_model("content", "SiteSettings")
    SocialLink = apps.get_model("content", "SocialLink")
    settings_row = SiteSettings.objects.filter(pk=1).first()
    if settings_row is None:
        return
    for field, name, group, order in CARRIED_OVER:
        url = getattr(settings_row, field, "") or ""
        SocialLink.objects.update_or_create(
            name=name,
            defaults={"url": url, "group": group, "order": order, "published": True},
        )


def put_links_back(apps, schema_editor):
    SiteSettings = apps.get_model("content", "SiteSettings")
    SocialLink = apps.get_model("content", "SocialLink")
    settings_row = SiteSettings.objects.filter(pk=1).first()
    if settings_row is None:
        return
    for field, name, _group, _order in CARRIED_OVER:
        link = SocialLink.objects.filter(name=name).first()
        setattr(settings_row, field, link.url if link else "")
    settings_row.save()


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SocialLink',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('published', models.BooleanField(default=True, help_text='Untick to hide this from the site.')),
                ('order', models.PositiveIntegerField(default=0, help_text='Lower numbers come first.')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(help_text='Shown as the link text. For example Facebook, LinkedIn, GitHub, Instagram, X, Discord, WhatsApp.', max_length=40)),
                ('url', models.URLField(blank=True, default='', help_text="Leave blank to list the platform with a 'Soon' badge instead of a link.")),
                ('group', models.CharField(choices=[('chat', 'Where we talk'), ('social', 'Follow us')], default='social', max_length=10)),
                ('handle', models.CharField(blank=True, default='', help_text='Optional. The account name, if it is worth showing. For example @kdudev.', max_length=80)),
            ],
            options={
                'verbose_name': 'social link',
                'verbose_name_plural': 'social links',
                'ordering': ['order', 'id'],
                'abstract': False,
            },
        ),
        migrations.RunPython(carry_links_over, put_links_back),
        migrations.RemoveField(
            model_name='sitesettings',
            name='discord_url',
        ),
        migrations.RemoveField(
            model_name='sitesettings',
            name='github_url',
        ),
        migrations.RemoveField(
            model_name='sitesettings',
            name='instagram_url',
        ),
        migrations.RemoveField(
            model_name='sitesettings',
            name='whatsapp_url',
        ),
    ]
