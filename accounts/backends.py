"""Sign in with an email address.

`User.username` holds the address already, so the stock backend nearly works;
what it does not do is match case-insensitively, and people do not type their
address the same way twice. This looks the account up on `email` instead.

The duplicate branch matters: `User.email` carries no unique constraint, so
two rows with the same address are possible if one is ever created outside the
sign-up form. Authenticating an ambiguous address would be a coin toss, so it
is refused instead.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        address = kwargs.get("email") or username
        if not address or password is None:
            return None

        try:
            user = UserModel.objects.get(email__iexact=address.strip())
        except UserModel.DoesNotExist:
            # Run the hasher anyway so a missing account and a wrong password
            # take the same time and cannot be told apart from the outside.
            UserModel().set_password(password)
            return None
        except UserModel.MultipleObjectsReturned:
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
