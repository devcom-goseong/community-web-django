"""Make the handle unique, now that every row has one."""

from django.db import migrations, models

import accounts.validators


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_fill_member_handles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="member",
            name="handle",
            field=models.SlugField(
                blank=True, max_length=30, unique=True,
                help_text="The end of the profile address, /members/<handle>/. Generated from "
                          "the name; the member can change it.",
                validators=[accounts.validators.validate_handle],
            ),
        ),
    ]
