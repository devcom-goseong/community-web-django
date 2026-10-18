"""Let the leadership team mark a member as a professor."""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_unique_email_ci'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='role',
            field=models.CharField(choices=[('member', 'Member'), ('professor', 'Professor')], db_index=True, default='member', help_text='Set by the leadership team. A professor is shown differently in the directory and on their own profile. It changes nothing about what they can do on the site.', max_length=12),
        ),
    ]
