"""Invite links, the members directory, profiles, approval, and closing an account.

Most of these are about who can see what, because that is where a mistake
hurts someone: an invite link in front of a spammer, or a member's details in
front of a stranger.
"""

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from content.models import InterestArea, Page, SocialLink

from .emails import make_token
from .factories import PASSWORD, make_member, make_staff
from .models import Member, MemberProject
from .services import change_status

UserModel = get_user_model()

TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "APP_URL": "https://community.example.org",
}

INVITE = "https://discord.gg/members-only-invite"


class Base(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []


@override_settings(**TEST_SETTINGS)
class InviteLinkTests(Base):
    def setUp(self):
        super().setUp()
        SocialLink.objects.create(name="Discord", group=SocialLink.GROUP_CHAT, url=INVITE,
                                  handle="kdu-server", members_only=True)
        SocialLink.objects.create(name="GitHub", group=SocialLink.GROUP_SOCIAL,
                                  url="https://github.com/devcom-goseong", members_only=False)

    def page_for(self, user):
        self.client.logout()
        if user is not None:
            self.client.force_login(user)
        return self.client.get(reverse("content:home"))

    def test_the_invite_address_is_not_in_the_page_for_anyone_who_is_not_a_member(self):
        people = {
            "anonymous": None,
            "unconfirmed": make_member("unconfirmed").user,
            "pending": make_member("pending").user,
            "paused": make_member("paused").user,
            "removed": make_member("removed").user,
        }
        for label, user in people.items():
            with self.subTest(who=label):
                response = self.page_for(user)
                self.assertNotContains(response, INVITE)
                self.assertNotContains(response, "kdu-server",
                                       msg_prefix="the handle can be an invite code too")
                self.assertContains(response, "Members")

    def test_members_and_staff_get_the_invite_address(self):
        for label, user in {"member": make_member("member").user, "staff": make_staff()}.items():
            with self.subTest(who=label):
                self.assertContains(self.page_for(user), INVITE)

    def test_a_deactivated_user_with_an_active_member_row_gets_nothing(self):
        member = make_member("member")
        member.user.is_active = False
        member.user.save()
        self.client.force_login(member.user)  # force_login ignores is_active
        self.assertNotContains(self.client.get(reverse("content:home")), INVITE)

    def test_public_links_are_shown_to_everyone(self):
        self.assertContains(self.page_for(None), "https://github.com/devcom-goseong")

    def test_the_account_page_lists_the_invites_for_members_only(self):
        member = make_member("member")
        self.client.force_login(member.user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Where we talk")
        self.assertContains(response, INVITE)

        pending = make_member("pending")
        self.client.force_login(pending.user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertNotContains(response, INVITE)
        self.assertContains(response, "being reviewed")

    def test_the_approval_email_does_not_contain_the_invite(self):
        member = make_member("pending")
        with self.captureOnCommitCallbacks(execute=True):
            change_status(member, Member.Status.ACTIVE)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn(INVITE, mail.outbox[0].body)
        self.assertNotIn(INVITE, mail.outbox[0].alternatives[0][0])


@override_settings(**TEST_SETTINGS)
class DirectoryAccessTests(Base):
    def test_anonymous_visitors_are_sent_to_sign_in(self):
        response = self.client.get(reverse("members:directory"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_people_who_are_not_members_yet_are_told_why(self):
        expectations = {
            "unconfirmed": "Confirm your email address",
            "pending": "waiting for the leadership team",
            "paused": "paused",
        }
        for state, explanation in expectations.items():
            with self.subTest(state=state):
                self.client.force_login(make_member(state).user)
                response = self.client.get(reverse("members:directory"))
                self.assertEqual(response.status_code, 403)
                self.assertContains(response, explanation, status_code=403)

    def test_members_and_staff_can_open_it(self):
        for user in (make_member("member").user, make_staff()):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("members:directory")).status_code, 200)

    def test_it_is_never_cached_or_indexed(self):
        self.client.force_login(make_member("member").user)
        response = self.client.get(reverse("members:directory"))
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertIn("private", response["Cache-Control"])
        self.assertContains(response, 'name="robots" content="noindex')


@override_settings(**TEST_SETTINGS)
class DirectoryListingTests(Base):
    def setUp(self):
        super().setUp()
        InterestArea.objects.create(name="Programming", order=0)
        InterestArea.objects.create(name="Design", order=1)
        self.viewer = make_member("member")
        self.client.force_login(self.viewer.user)

    def listing(self, **params):
        return self.client.get(reverse("members:directory"), params)

    def test_only_approved_members_who_chose_to_be_listed_appear(self):
        listed = make_member("member", name="Listed Person", visibility=Member.Visibility.MEMBERS)
        public = make_member("member", name="Public Person", visibility=Member.Visibility.PUBLIC)
        hidden = make_member("member", name="Hidden Person")
        pending = make_member("pending", name="Pending Person", visibility=Member.Visibility.MEMBERS)
        unconfirmed = make_member("unconfirmed", name="Unconfirmed Person",
                                  visibility=Member.Visibility.MEMBERS)
        paused = make_member("paused", name="Paused Person", visibility=Member.Visibility.MEMBERS)
        inactive = make_member("member", name="Deactivated Person",
                               visibility=Member.Visibility.MEMBERS)
        inactive.user.is_active = False
        inactive.user.save()

        response = self.listing()
        for shown in (listed, public):
            self.assertContains(response, shown.display_name)
        for not_shown in (hidden, pending, unconfirmed, paused, inactive):
            self.assertNotContains(response, not_shown.display_name)

    def test_email_addresses_and_student_details_are_never_shown(self):
        make_member("member", name="Careful Person", visibility=Member.Visibility.PUBLIC,
                    email="careful@example.org", student="yes", student_id="20269999")
        response = self.listing()
        self.assertContains(response, "Careful Person")
        self.assertNotContains(response, "careful@example.org")
        self.assertNotContains(response, "20269999")

    def test_search_by_name_handle_and_introduction(self):
        make_member("member", name="Ada Lovelace", visibility=Member.Visibility.MEMBERS,
                    bio="Engines and notes.")
        make_member("member", name="Grace Hopper", visibility=Member.Visibility.MEMBERS)
        self.assertContains(self.listing(q="lovelace"), "Ada Lovelace")
        self.assertNotContains(self.listing(q="lovelace"), "Grace Hopper")
        self.assertContains(self.listing(q="engines"), "Ada Lovelace")

    def test_filtering_by_interest(self):
        make_member("member", name="Coder", visibility=Member.Visibility.MEMBERS,
                    interests=["Programming"])
        make_member("member", name="Designer", visibility=Member.Visibility.MEMBERS,
                    interests=["Design"])
        response = self.listing(interest="Design")
        self.assertContains(response, "Designer")
        self.assertNotContains(response, "Coder")

    def test_it_pages(self):
        for n in range(30):
            make_member("member", name=f"Member {n:02d}", visibility=Member.Visibility.MEMBERS)
        first = self.listing()
        self.assertContains(first, "Page 1 of 2")
        second = self.listing(page=2)
        self.assertContains(second, "Member 29")
        self.assertEqual(self.listing(page="nonsense").status_code, 200)


@override_settings(**TEST_SETTINGS)
class ProfileVisibilityTests(Base):
    def view(self, member, as_user):
        self.client.logout()
        if as_user is not None:
            self.client.force_login(as_user)
        return self.client.get(member.get_absolute_url())

    def test_who_sees_what(self):
        hidden = make_member("member", visibility=Member.Visibility.HIDDEN)
        members = make_member("member", visibility=Member.Visibility.MEMBERS)
        public = make_member("member", visibility=Member.Visibility.PUBLIC)
        other = make_member("member").user
        pending = make_member("pending").user
        staff = make_staff()

        cases = [
            (hidden, hidden.user, 200), (hidden, staff, 200), (hidden, other, 404),
            (hidden, None, 404),
            (members, other, 200), (members, staff, 200), (members, pending, 404),
            (members, None, 404),
            (public, None, 200), (public, pending, 200), (public, other, 200),
        ]
        for member, viewer, expected in cases:
            with self.subTest(visibility=member.profile_visibility,
                              viewer=getattr(viewer, "email", "anonymous")):
                self.assertEqual(self.view(member, viewer).status_code, expected)

    def test_a_paused_members_page_disappears_whatever_it_was_set_to(self):
        member = make_member("member", visibility=Member.Visibility.PUBLIC)
        change_status(member, Member.Status.PAUSED)
        self.assertEqual(self.view(member, None).status_code, 404)
        self.assertEqual(self.view(member, member.user).status_code, 200, "the owner still can")

    def test_not_found_and_not_allowed_look_the_same(self):
        hidden = make_member("member")
        missing = self.client.get(reverse("members:profile", args=["nobody-by-this-name"]))
        refused = self.view(hidden, None)
        self.assertEqual(missing.status_code, refused.status_code)
        self.assertNotContains(refused, hidden.display_name, status_code=404)

    def test_a_capitalised_address_redirects_to_the_real_one(self):
        member = make_member("member", visibility=Member.Visibility.PUBLIC)
        response = self.client.get(f"/members/{member.handle.upper()}/")
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.url, member.get_absolute_url())

    def test_a_profile_is_never_indexed_and_never_shows_private_details(self):
        member = make_member("member", visibility=Member.Visibility.PUBLIC,
                             email="private@example.org", student_id="20261234",
                             github_url="https://github.com/someone")
        response = self.view(member, None)
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.assertNotContains(response, "private@example.org")
        self.assertNotContains(response, "20261234")
        self.assertContains(response, 'rel="nofollow ugc noopener noreferrer"')

    def test_the_owner_is_told_who_can_see_it(self):
        member = make_member("member", visibility=Member.Visibility.HIDDEN)
        self.assertContains(self.view(member, member.user), "Only you and the leadership team")


class ProfilePostMixin:
    def profile_post(self, member, **overrides):
        data = {
            "display_name": member.display_name, "handle": member.handle,
            "profile_visibility": member.profile_visibility, "bio": "", "github_url": "",
            "linkedin_url": "", "student": "", "student_id": "",
            "projects-TOTAL_FORMS": "0", "projects-INITIAL_FORMS": "0",
            "projects-MIN_NUM_FORMS": "0", "projects-MAX_NUM_FORMS": "8",
        }
        data.update(overrides)
        self.client.force_login(member.user)
        return self.client.post(reverse("accounts:profile_edit"), data)


@override_settings(**TEST_SETTINGS)
class HandleTests(ProfilePostMixin, Base):
    def test_a_handle_comes_from_the_name(self):
        self.assertEqual(make_member(name="Sam Park").handle, "sam-park")

    def test_the_same_name_twice_gets_two_different_handles(self):
        first = make_member(name="Sam Park")
        second = make_member(name="Sam Park")
        self.assertNotEqual(first.handle, second.handle)
        self.assertTrue(second.handle.startswith("sam-park-"))

    def test_a_korean_name_still_gets_a_working_profile_address(self):
        member = make_member("member", name="김민수", visibility=Member.Visibility.PUBLIC)
        self.assertRegex(member.handle, r"^member-[0-9a-f]{6}$")
        response = self.client.get(member.get_absolute_url())
        self.assertContains(response, "김민수")

    def test_choosing_a_handle(self):
        member = make_member("member")
        self.assertEqual(self.profile_post(member, handle="Ada-Codes").status_code, 302)
        member.refresh_from_db()
        self.assertEqual(member.handle, "ada-codes", "stored in lowercase")

    def test_handles_that_are_refused(self):
        make_member(name="Taken Name")
        member = make_member("member")
        for bad in ("me", "admin", "a", "has space", "bad--hyphens", "-edge", "taken-name",
                    "TAKEN-NAME", "x" * 31, "한글"):
            with self.subTest(handle=bad):
                response = self.profile_post(member, handle=bad)
                self.assertEqual(response.status_code, 200)
                member.refresh_from_db()
                self.assertNotEqual(member.handle, bad.lower())


@override_settings(**TEST_SETTINGS)
class ProfileLinkTests(ProfilePostMixin, Base):
    def test_github_and_linkedin_must_be_those_sites(self):
        member = make_member("member")
        refused = {
            "github_url": ["https://evil.example/github.com", "javascript:alert(1)",
                           "https://github.com.evil.example/x"],
            "linkedin_url": ["https://evil-linkedin.com/in/x", "ftp://linkedin.com/in/x"],
        }
        for field, values in refused.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.profile_post(member, **{field: value})
                    member.refresh_from_db()
                    self.assertEqual(getattr(member, field), "")

        self.profile_post(member, github_url="https://github.com/ada",
                          linkedin_url="https://kr.linkedin.com/in/ada")
        member.refresh_from_db()
        self.assertEqual(member.github_url, "https://github.com/ada")
        self.assertEqual(member.linkedin_url, "https://kr.linkedin.com/in/ada")

    def test_projects_can_be_added_removed_and_are_capped(self):
        member = make_member("member", visibility=Member.Visibility.PUBLIC)
        self.profile_post(member, **{
            "projects-TOTAL_FORMS": "1",
            "projects-0-title": "A compiler", "projects-0-url": "https://github.com/ada/c",
            "projects-0-description": "Small and slow.",
        })
        project = MemberProject.objects.get(member=member)
        self.assertContains(self.client.get(member.get_absolute_url()), "A compiler")

        self.profile_post(member, **{
            "projects-TOTAL_FORMS": "2", "projects-INITIAL_FORMS": "1",
            "projects-0-id": str(project.pk), "projects-0-member": str(member.pk),
            "projects-0-title": "A compiler", "projects-0-url": "https://github.com/ada/c",
            "projects-0-description": "", "projects-0-DELETE": "on",
            "projects-1-title": "A website", "projects-1-url": "", "projects-1-description": "",
        })
        self.assertEqual(list(member.projects.values_list("title", flat=True)), ["A website"])

        data = {"projects-TOTAL_FORMS": "9"}
        for i in range(9):
            data[f"projects-{i}-title"] = f"Project {i}"
        self.profile_post(member, **data)
        self.assertLessEqual(member.projects.count(), 8)

    def test_a_project_link_must_be_a_web_address(self):
        member = make_member("member")
        self.profile_post(member, **{
            "projects-TOTAL_FORMS": "1", "projects-0-title": "Sneaky",
            "projects-0-url": "javascript:alert(1)",
        })
        self.assertFalse(member.projects.exists())


@override_settings(**TEST_SETTINGS)
class ApprovalTests(Base):
    def admin_action(self, action, *members):
        admin = make_staff()
        admin.is_superuser = True
        admin.save()
        self.client.force_login(admin)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("admin:accounts_member_changelist"), {
                "action": action, "_selected_action": [str(m.pk) for m in members],
                "index": "0", "select_across": "0",
            })

    def test_approving_sets_the_date_and_sends_one_email(self):
        member = make_member("pending")
        self.admin_action("approve", member)
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.ACTIVE)
        self.assertIsNotNone(member.approved_at)
        self.assertEqual([m.to for m in mail.outbox], [[member.email]])

    def test_approving_someone_unconfirmed_waits_to_email_until_they_confirm(self):
        member = make_member("unconfirmed")
        self.admin_action("approve", member)
        self.assertEqual(mail.outbox, [])

        self.client.logout()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.get(reverse("accounts:verify", args=[make_token(member.user)]))
        self.assertContains(response, "You are a member")
        self.assertEqual(len(mail.outbox), 1)

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(reverse("accounts:verify", args=[make_token(member.user)]))
        self.assertEqual(len(mail.outbox), 1, "clicking the link again does not email again")

    def test_removing_hides_the_profile(self):
        member = make_member("member", visibility=Member.Visibility.PUBLIC)
        self.admin_action("remove", member)
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.REMOVED)
        self.assertEqual(member.profile_visibility, Member.Visibility.HIDDEN)

    def test_accepting_an_application_approves_a_confirmed_account(self):
        member = make_member("pending", email="Applicant@Example.org")
        application = Application.objects.create(
            name="Applicant", email="applicant@example.org", intent=Application.Intent.JOIN)
        admin = make_staff()
        admin.is_superuser = True
        admin.save()
        self.client.force_login(admin)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("admin:applications_application_changelist"), {
                "action": "mark_accepted", "_selected_action": [str(application.pk)],
                "index": "0", "select_across": "0",
            })
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.ACTIVE)

    def test_a_question_does_not_approve_anyone(self):
        member = make_member("pending", email="asker@example.org")
        Application.objects.create(name="Asker", email="asker@example.org",
                                   intent=Application.Intent.QUESTION,
                                   status=Application.Status.ACCEPTED)
        from .services import approve_if_already_accepted

        self.assertFalse(approve_if_already_accepted(member))

    def test_an_accepted_applicant_who_signs_up_later_is_approved_on_confirming(self):
        Application.objects.create(name="Later", email="later@example.org",
                                   intent=Application.Intent.JOIN,
                                   status=Application.Status.ACCEPTED)
        member = make_member("unconfirmed", email="later@example.org")
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.PENDING,
                         "not before the address is proven, or anyone could claim the approval")

        with self.captureOnCommitCallbacks(execute=True):
            self.client.get(reverse("accounts:verify", args=[make_token(member.user)]))
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.ACTIVE)


@override_settings(**TEST_SETTINGS)
class CloseAccountTests(Base):
    def test_the_wrong_password_closes_nothing(self):
        member = make_member("member")
        self.client.force_login(member.user)
        response = self.client.post(reverse("accounts:close"), {"password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserModel.objects.filter(pk=member.user_id).exists())

    def test_closing_deletes_everything_and_signs_out(self):
        member = make_member("member")
        MemberProject.objects.create(member=member, title="Mine")
        Application.objects.create(name="Me", email=member.email)
        self.client.force_login(member.user)

        response = self.client.post(reverse("accounts:close"), {"password": PASSWORD})
        self.assertRedirects(response, reverse("content:home"))
        self.assertFalse(UserModel.objects.filter(pk=member.user_id).exists())
        self.assertFalse(Member.objects.filter(pk=member.pk).exists())
        self.assertFalse(MemberProject.objects.exists())
        self.assertTrue(Application.objects.exists(), "kept unless they asked")
        self.assertFalse(self.client.get(reverse("accounts:dashboard")).wsgi_request.user.is_authenticated)

    def test_closing_can_take_the_applications_with_it(self):
        member = make_member("member", email="gone@example.org")
        Application.objects.create(name="Me", email="GONE@example.org")
        Application.objects.create(name="Someone else", email="other@example.org")
        self.client.force_login(member.user)
        self.client.post(reverse("accounts:close"),
                         {"password": PASSWORD, "delete_applications": "on"})
        self.assertEqual(list(Application.objects.values_list("email", flat=True)),
                         ["other@example.org"])

    def test_leadership_accounts_cannot_close_themselves_here(self):
        staff = make_staff(with_member=True)
        self.client.force_login(staff)
        self.client.post(reverse("accounts:close"), {"password": PASSWORD})
        self.assertTrue(UserModel.objects.filter(pk=staff.pk).exists())


@override_settings(**TEST_SETTINGS)
class SiteGuardTests(Base):
    def test_robots_keeps_crawlers_out_of_member_areas(self):
        body = self.client.get("/robots.txt").content.decode()
        for path in ("/account/", "/members/", "/admin/"):
            self.assertIn(f"Disallow: {path}", body)
        self.assertNotIn("Disallow: /events/", body)

    def test_a_page_cannot_take_an_address_the_site_already_uses(self):
        from django.core.exceptions import ValidationError

        for slug in ("events", "members", "account"):
            with self.subTest(slug=slug), self.assertRaises(ValidationError):
                Page(slug=slug, title="Clash", lead="x").full_clean()

    def test_the_welcome_email_links_to_this_app_not_the_static_site(self):
        member = make_member("unconfirmed")
        from .emails import send_welcome_email

        send_welcome_email(member)  # no request, as from a script
        self.assertIn("https://community.example.org/account/verify/", mail.outbox[0].body)

    def test_the_deployment_check_catches_a_localhost_app_url(self):
        from .checks import app_url_is_real

        with self.settings(DEBUG=False, APP_URL="http://localhost:8000"):
            self.assertEqual([w.id for w in app_url_is_real(None)], ["accounts.W001"])
        with self.settings(DEBUG=False, APP_URL="https://community.example.org"):
            self.assertEqual(app_url_is_real(None), [])


@override_settings(**TEST_SETTINGS)
class SignUpStillWorksTests(Base):
    def test_the_whole_way_in(self):
        InterestArea.objects.create(name="Programming", order=0)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("accounts:signup"), {
                "display_name": "New Person", "email": "new@example.org", "student": "no",
                "student_id": "", "password1": PASSWORD, "password2": PASSWORD,
                "accepted_documents": "on",
            })
        self.assertRedirects(response, reverse("accounts:dashboard"))
        member = Member.objects.get(user__email="new@example.org")
        self.assertEqual(member.handle, "new-person")
        self.assertEqual(member.profile_visibility, Member.Visibility.HIDDEN,
                         "nobody is listed without choosing to be")
        self.assertIsNone(member.approved_at)
        self.assertLess(member.accepted_at, timezone.now())


@override_settings(**TEST_SETTINGS)
class AdminSafetyTests(Base):
    def test_member_rows_cannot_be_deleted_on_their_own(self):
        from django.contrib.admin.sites import site

        from .admin import MemberAdmin

        self.assertFalse(MemberAdmin(Member, site).has_delete_permission(None))

    def test_a_login_with_no_member_row_is_not_sent_to_the_admin(self):
        user = UserModel.objects.create_user(username="orphan@example.org",
                                             email="orphan@example.org", password=PASSWORD)
        self.client.force_login(user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertRedirects(response, reverse("content:home"))


@override_settings(**TEST_SETTINGS)
class ApplicationPrivacyTests(Base):
    def test_applications_are_not_shown_until_the_address_is_proven(self):
        Application.objects.create(name="Victim", email="victim@example.org",
                                   intent=Application.Intent.JOIN,
                                   status=Application.Status.DECLINED)
        impostor = make_member("unconfirmed", email="victim@example.org")
        self.client.force_login(impostor.user)
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertNotContains(response, "Declined")
        self.assertNotContains(response, "Membership application")

        impostor.mark_verified()
        self.assertContains(self.client.get(reverse("accounts:dashboard")), "Declined")
