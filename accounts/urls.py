from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("sign-up/", views.signup, name="signup"),
    path("sign-in/", views.SignIn.as_view(), name="login"),
    path("sign-out/", views.SignOut.as_view(), name="logout"),
    path("me/", views.dashboard, name="dashboard"),
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
    ), name="password_reset"),
    path("password/reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_sent.html",
    ), name="password_reset_done"),
    path("password/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url="/account/password/reset/done/",
    ), name="password_reset_confirm"),
    path("password/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_done.html",
    ), name="password_reset_complete"),
    path("password/change/", auth_views.PasswordChangeView.as_view(
        template_name="accounts/password_change.html",
        success_url="/account/password/changed/",
    ), name="password_change"),
    path("password/changed/", auth_views.PasswordChangeDoneView.as_view(
        template_name="accounts/password_changed.html",
    ), name="password_change_done"),
]
