"""Profiles: a handle, a visibility setting, an approval date, and projects.

This is the first of three migrations, and the split is deliberate. The handle
has to be unique, but existing rows have no handle yet. Adding the column,
filling it and then making it unique all in one migration would mean altering
the table in the same transaction that has just updated its rows, and on
PostgreSQL that fails with "cannot ALTER TABLE because it has pending trigger
events" (the foreign key to the user table is checked at commit). An empty test
database never hits it; a real one with members in it does.
"""

import django.utils.timezone
from django.db import migrations, models

import accounts.validators


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="handle",
            field=models.SlugField(
                blank=True, default="", max_length=30,
                help_text="The end of the profile address, /members/<handle>/. Generated from "
                          "the name; the member can change it.",
                validators=[accounts.validators.validate_handle],
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="member",
            name="profile_visibility",
            field=models.CharField(
                choices=[("hidden", "Only me (and the leadership team)"),
                         ("members", "Members of the community"),
                         ("public", "Anyone with the link")],
                default="hidden", max_length=10,
                help_text="Who can see the profile page. 'Members' and 'Anyone with the link' "
                          "also list the member in the members directory.",
            ),
        ),
        migrations.AddField(
            model_name="member",
            name="approved_at",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="When they first became a member. Set automatically on approval.",
            ),
        ),
        migrations.AlterField(
            model_name="member",
            name="bio",
            field=models.TextField(
                blank=True, default="", max_length=600,
                help_text="A short introduction. Shown on the profile, to whoever the profile "
                          "visibility allows.",
            ),
        ),
        migrations.AlterField(
            model_name="member",
            name="github_url",
            field=models.URLField(
                blank=True, default="", validators=[accounts.validators.validate_github_url]),
        ),
        migrations.AlterField(
            model_name="member",
            name="linkedin_url",
            field=models.URLField(
                blank=True, default="", validators=[accounts.validators.validate_linkedin_url]),
        ),
        migrations.CreateModel(
            name="MemberProject",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name="ID")),
                ("title", models.CharField(max_length=80)),
                ("url", models.URLField(
                    blank=True, default="",
                    help_text="Optional. Where people can see it: a repository, a demo, a "
                              "write-up.",
                    validators=[accounts.validators.validate_web_url], verbose_name="link")),
                ("description", models.CharField(
                    blank=True, default="", help_text="Optional. One sentence.",
                    max_length=200)),
                ("order", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("member", models.ForeignKey(
                    on_delete=models.CASCADE, related_name="projects",
                    to="accounts.member")),
            ],
            options={
                "verbose_name": "project",
                "verbose_name_plural": "projects",
                "ordering": ["order", "pk"],
            },
        ),
    ]
