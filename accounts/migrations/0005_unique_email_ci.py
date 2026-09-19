"""A database-level guarantee that no two accounts share an email address.

The sign-up form already rejects an address that is taken, and the login
backend refuses to authenticate an ambiguous one, but until now nothing stopped
a second row with the same address being created outside the form — from the
admin, a management command, or a shell. This adds a case-insensitive unique
index on the address so the guarantee holds however the account is made.

Blank addresses are excluded: an account may legitimately have none (a stock
superuser created without one), and several of those must not collide. The same
SQL runs on SQLite (production) and PostgreSQL (CI): both support a unique index
on lower(email) with a partial WHERE.
"""

from django.db import migrations


class Migration(migrations.Migration):

    # Depend on the last auth migration, not just our own. Several auth
    # migrations alter the auth_user table (username/first_name/last_name field
    # lengths), and on SQLite an AlterField rebuilds the table, recreating only
    # the indexes Django holds in model state — which would drop this raw index
    # if it were created first. Running after them keeps it.
    dependencies = [
        ("accounts", "0004_member_handle_unique"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(
            sql="CREATE UNIQUE INDEX IF NOT EXISTS accounts_user_email_ci "
                "ON auth_user (lower(email)) WHERE email <> '';",
            reverse_sql="DROP INDEX IF EXISTS accounts_user_email_ci;",
        ),
    ]
