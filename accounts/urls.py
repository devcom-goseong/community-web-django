from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("sign-up/", views.signup, name="signup"),
    path("sign-in/", views.SignIn.as_view(), name="login"),
    path("sign-out/", views.SignOut.as_view(), name="logout"),
    path("me/", views.dashboard, name="dashboard"),
    path("profile/", views.profile_edit, name="profile_edit"),
    path("close/", views.close_account, name="close"),
    # Order matters: "resend" would otherwise be read as a token by the
    # route below and answered by a GET-only view.
    path("verify/resend/", views.resend_verification, name="resend_verification"),
    path("verify/<str:token>/", views.verify, name="verify"),

    # Password reset, using Django's own views with this site's templates.
    path("password/reset/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset.html",
        email_template_name="accounts/password_reset_email.txt",
        subject_template_name="accounts/password_reset_subject.txt",
        success_url="/account/password/reset/sent/",
        extra_context={"page_title": "Reset your password", "page_description": "Get a link to set a new password.", "nav": "account", "noindex": True},
    ), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_sent.html",
        extra_context={"page_title": "Check your inbox", "page_description": "A password reset link is on its way.", "nav": "account", "noindex": True},
    ), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url="/account/password/reset/done/",
        extra_context={"page_title": "Set a new password", "page_description": "Choose a new password for your account.", "nav": "account", "noindex": True},
    ), name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_done.html",
        extra_context={"page_title": "Password changed", "page_description": "Your password has been changed.", "nav": "account", "noindex": True},
    ), name="password_reset_complete"),
    path("password/change/", auth_views.PasswordChangeView.as_view(
        template_name="accounts/password_change.html",
        success_url="/account/password/changed/",
        extra_context={"page_title": "Change your password", "page_description": "Change the password for your account.", "nav": "account", "noindex": True},
    ), name="password_change"),
    path("password/changed/", auth_views.PasswordChangeDoneView.as_view(
        template_name="accounts/password_changed.html",
        extra_context={"page_title": "Password changed", "page_description": "Your password has been changed.", "nav": "account", "noindex": True},
    ), name="password_change_done"),
]
