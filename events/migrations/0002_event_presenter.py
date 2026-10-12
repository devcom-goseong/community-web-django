"""Record who is presenting an event, for the weekly meetings."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='presenter',
            field=models.CharField(blank=True, default='', help_text='Who is presenting or leading this one. A plain name rather than a member account, so a guest who has not joined can be named too. Leave it blank when nobody in particular is presenting.', max_length=120),
        ),
    ]
