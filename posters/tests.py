"""Talk posters: the presenter's link, the form, the poster, and who can see it when."""

import io
import json
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.factories import make_member
from events.models import Event

from . import services
from .models import Platform, TalkPoster
from .render import HEIGHT, WIDTH, PosterContent, render

MEDIA = tempfile.mkdtemp(prefix="kdu-posters-tests-")
TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "APP_URL": "https://community.example.org",
    "TEAM_INBOX": "team@example.org",
    "MEDIA_ROOT": MEDIA,
}

# Drawing a real poster takes about a second, so most tests use this stand-in
# and RenderTests draws real ones.
TINY_PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00"
            b"\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7"
            b"\x9a\xa0\xa0\x00\x00\x00\x00IEND\xaeB`\x82")


def photo_upload(size=(600, 900), name="me.jpg", exif=None):
    picture = Image.new("RGB", size, (200, 120, 90))
    out = io.BytesIO()
    picture.save(out, "JPEG", **({"exif": exif} if exif else {}))
    return SimpleUploadedFile(name, out.getvalue(), content_type="image/jpeg")


def make_talk(**fields):
    start = timezone.now() + timedelta(days=7)
    data = {"starts_at": start, "ends_at": start + timedelta(hours=1)}
    data.update(fields)
    return TalkPoster.objects.create(**data)


FILLED = {
    "title": "What makes a designer in 2026?",
    "summary": "A look at the future of design.",
    "about": "Where to start, and where design is going.",
    "speaker_name": "Ndikuriyo Don Christ Ajax",
    "speaker_tag": "KDU Alumni",
}


def submitted_talk(**fields):
    talk = make_talk(**{**FILLED, **fields})
    services.store_photo(talk, photo_upload())
    with mock.patch("posters.services.render", return_value=TINY_PNG):
        services.draw(talk)
    talk.status = TalkPoster.Status.SUBMITTED
    talk.submitted_at = timezone.now()
    talk.save()
    return talk


class MediaTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cache.clear()


@override_settings(**TEST_SETTINGS)
class PresenterLinkTests(MediaTestCase):
    def post(self, talk, **overrides):
        data = {**FILLED, "photo": photo_upload(), **overrides}
        with mock.patch("posters.services.render", return_value=TINY_PNG):
            with self.captureOnCommitCallbacks(execute=True):
                return self.client.post(talk.get_absolute_url(), data)

    def test_an_unknown_link_says_it_does_not_work(self):
        resp = self.client.get(reverse("posters:present", args=["not-a-real-token"]))
        self.assertContains(resp, "This link does not work", status_code=404)

    def test_an_expired_link_says_so(self):
        talk = make_talk(link_expires_at=timezone.now() - timedelta(minutes=1))
        self.assertContains(self.client.get(talk.get_absolute_url()), "has expired",
                            status_code=410)

    def test_the_page_shows_the_time_and_place_the_team_set_and_is_not_indexed(self):
        talk = make_talk(platform=Platform.ZOOM)
        resp = self.client.get(talk.get_absolute_url())
        self.assertContains(resp, "Online, on Zoom")
        self.assertContains(resp, 'name="robots" content="noindex')
        self.assertEqual(resp["X-Robots-Tag"], "noindex")
        self.assertNotContains(resp, 'name="starts_at"')

    def test_every_field_and_the_photo_are_required(self):
        talk = make_talk()
        resp = self.client.post(talk.get_absolute_url(), {})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.context["form"].errors),
                         {"title", "summary", "about", "speaker_name", "speaker_tag", "photo"})
        talk.refresh_from_db()
        self.assertEqual(talk.status, TalkPoster.Status.WAITING)

    def test_text_the_poster_cannot_print_is_refused_by_name(self):
        resp = self.post(make_talk(), speaker_name="돈 아작")
        self.assertIn("돈 아 작", resp.context["form"].errors["speaker_name"][0])

    def test_a_photo_too_small_to_print_sharply_is_refused(self):
        resp = self.post(make_talk(), photo=photo_upload(size=(300, 300)))
        self.assertIn("300×300", resp.context["form"].errors["photo"][0])

    def test_a_file_that_is_not_a_photo_is_refused(self):
        fake = SimpleUploadedFile("me.jpg", b"not a picture", content_type="image/jpeg")
        resp = self.post(make_talk(), photo=fake)
        self.assertIn("photo", resp.context["form"].errors)

    def test_sending_it_draws_the_poster_closes_the_link_and_tells_the_team(self):
        talk = make_talk()
        resp = self.post(talk)
        self.assertContains(resp, "your poster is made")
        self.assertContains(resp, "data:image/png;base64,")

        talk.refresh_from_db()
        self.assertEqual(talk.status, TalkPoster.Status.SUBMITTED)
        self.assertIsNotNone(talk.submitted_at)
        self.assertEqual(talk.title, FILLED["title"])
        self.assertTrue(talk.poster.storage.exists(talk.poster.name))

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["team@example.org"])
        self.assertIn(FILLED["title"], message.subject)
        self.assertIn(reverse("admin:posters_talkposter_change", args=[talk.pk]), message.body)
        self.assertEqual(message.attachments[0][2], "image/png")

        again = self.client.get(talk.get_absolute_url())
        self.assertContains(again, "already been used", status_code=410)

    def test_the_photo_is_kept_upright_and_without_its_exif(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # "rotate 90° clockwise to view", as phones write it
        exif[0x010F] = "Phone maker"
        talk = make_talk()
        self.post(talk, photo=photo_upload(size=(900, 600), exif=exif.tobytes()))
        talk.refresh_from_db()
        with talk.photo.open("rb") as stored, Image.open(stored) as picture:
            self.assertEqual(picture.size, (600, 900))
            self.assertEqual(len(picture.getexif()), 0)

    def test_a_new_link_keeps_the_answers_and_the_photo(self):
        talk = submitted_talk()
        old_photo = talk.photo.name
        talk.give_new_link()
        talk.save()
        resp = self.client.get(talk.get_absolute_url())
        self.assertContains(resp, FILLED["title"])
        self.post(talk, title="A better title", photo="")
        talk.refresh_from_db()
        self.assertEqual(talk.status, TalkPoster.Status.SUBMITTED)
        self.assertEqual((talk.title, talk.photo.name), ("A better title", old_photo))


@override_settings(**TEST_SETTINGS)
class ApproveTests(MediaTestCase):
    def setUp(self):
        super().setUp()
        self.admin = get_user_model().objects.create_superuser(
            "boss", "boss@example.org", "x-not-a-real-password")
        self.client.force_login(self.admin)

    def make_event(self, **fields):
        start = timezone.now() + timedelta(days=7)
        data = {"title": "Weekly meeting", "summary": "Every week.", "starts_at": start,
                "ends_at": start + timedelta(hours=1), "status": Event.Status.PUBLISHED}
        data.update(fields)
        return Event.objects.create(**data)

    def test_making_a_link_for_an_event_copies_its_date_and_time(self):
        event = self.make_event()
        resp = self.client.post(reverse("admin:posters_talkposter_add"), {
            "event": event.pk, "label": "Weekly meeting", "platform": Platform.GOOGLE_MEET,
            "place": "", "place_detail": "",
            "link_expires_at_0": "01/01/2099", "link_expires_at_1": "12:00",
            "starts_at_0": "", "starts_at_1": "", "ends_at_0": "", "ends_at_1": "",
        })
        talk = TalkPoster.objects.get()
        self.assertRedirects(resp, reverse("admin:posters_talkposter_change", args=[talk.pk]))
        self.assertEqual((talk.starts_at, talk.ends_at), (event.starts_at, event.ends_at))
        self.assertEqual(talk.created_by, self.admin)
        page = self.client.get(resp.url)
        self.assertContains(page, f"https://community.example.org{talk.get_absolute_url()}")

    def test_in_person_needs_a_room(self):
        start = timezone.localtime(timezone.now() + timedelta(days=3))
        resp = self.client.post(reverse("admin:posters_talkposter_add"), {
            "event": "", "label": "Workshop", "platform": Platform.IN_PERSON,
            "place": "", "place_detail": "",
            "starts_at_0": f"{start:%d/%m/%Y}", "starts_at_1": "11:00",
            "ends_at_0": f"{start:%d/%m/%Y}", "ends_at_1": "12:00",
            "link_expires_at_0": "01/01/2099", "link_expires_at_1": "12:00",
        })
        self.assertIn("place", resp.context["adminform"].form.errors)
        self.assertFalse(TalkPoster.objects.exists())

    def test_approving_onto_an_event_puts_the_poster_on_its_page(self):
        event = self.make_event()
        talk = submitted_talk()
        poster_url = reverse("events:poster", args=[event.slug])
        self.client.logout()
        self.assertEqual(self.client.get(poster_url).status_code, 404)

        self.client.force_login(self.admin)
        self.client.post(reverse("admin:posters_talkposter_approve", args=[talk.pk]),
                         {"choice": "attach", "event": event.pk})
        talk.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual((talk.status, talk.event), (TalkPoster.Status.APPROVED, event))
        self.assertEqual(event.presenter, FILLED["speaker_name"])

        self.client.logout()
        resp = self.client.get(poster_url)
        self.assertEqual((resp.status_code, resp["Content-Type"]), (200, "image/png"))
        page = self.client.get(event.get_absolute_url())
        # Small, inside the box with the time and place.
        self.assertContains(page, 'class="panel mt-7 event-panel"')
        self.assertContains(page, 'class="event-poster')
        self.assertContains(page, f'property="og:image" content="http://testserver{poster_url}')
        ld = json.loads(page.content.decode().split('application/ld+json">')[2]
                        .split("</script>")[0])
        self.assertTrue(ld["image"][0].startswith(f"http://testserver{poster_url}"))

    def test_approving_can_make_the_event_from_the_poster(self):
        talk = submitted_talk(platform=Platform.IN_PERSON, place="Room 301",
                              place_detail="Engineering")
        resp = self.client.post(reverse("admin:posters_talkposter_approve", args=[talk.pk]),
                                {"choice": "create", "status": Event.Status.DRAFT})
        event = Event.objects.get()
        self.assertRedirects(resp, reverse("admin:events_event_change", args=[event.pk]))
        self.assertEqual(
            (event.title, event.summary, event.description, event.presenter, event.location,
             event.starts_at, event.status),
            (FILLED["title"], FILLED["summary"], FILLED["about"], FILLED["speaker_name"],
             "Room 301, Engineering", talk.starts_at, Event.Status.DRAFT))
        # A draft is the team's alone, and so is its poster.
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("events:poster", args=[event.slug])).status_code, 404)

    def test_a_members_only_events_poster_is_for_members(self):
        event = self.make_event(visibility=Event.Visibility.MEMBERS)
        services.approve(submitted_talk(), self.admin, event)
        url = reverse("events:poster", args=[event.slug])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(make_member().user)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("private", resp["Cache-Control"])

    def test_nothing_to_approve_until_the_presenter_has_sent_the_form(self):
        talk = make_talk()
        resp = self.client.get(reverse("admin:posters_talkposter_approve", args=[talk.pk]))
        self.assertRedirects(resp, reverse("admin:posters_talkposter_change", args=[talk.pk]))

    def test_an_admin_edit_draws_the_poster_again(self):
        talk = submitted_talk()
        before = talk.poster.name
        change = reverse("admin:posters_talkposter_change", args=[talk.pk])
        form = self.client.get(change).context["adminform"].form
        data = {name: value for name, value in form.initial.items()
                if value is not None and name != "photo"}
        start, end = timezone.localtime(talk.starts_at), timezone.localtime(talk.ends_at)
        expires = timezone.localtime(talk.link_expires_at)
        data.update({
            "title": "Fixed typo", "event": "",
            "starts_at_0": f"{start:%d/%m/%Y}", "starts_at_1": f"{start:%H:%M}",
            "ends_at_0": f"{end:%d/%m/%Y}", "ends_at_1": f"{end:%H:%M}",
            "link_expires_at_0": f"{expires:%d/%m/%Y}", "link_expires_at_1": f"{expires:%H:%M}",
        })
        with mock.patch("posters.services.render", return_value=TINY_PNG) as drawn:
            resp = self.client.post(change, data)
        self.assertEqual(resp.status_code, 302, getattr(resp, "context", None)
                         and resp.context["adminform"].form.errors)
        talk.refresh_from_db()
        self.assertEqual(talk.title, "Fixed typo")
        self.assertNotEqual(talk.poster.name, before)
        self.assertEqual(drawn.call_args.args[0].title, "Fixed typo")


@override_settings(**TEST_SETTINGS)
class StaffFileTests(MediaTestCase):
    def test_uploaded_files_are_for_the_team_only(self):
        talk = submitted_talk()
        url = talk.photo.url
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(make_member().user)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(get_user_model().objects.create_user(
            "staff", "staff@example.org", "x-not-a-real-password", is_staff=True))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get("/media/../config/settings.py").status_code, 404)

    def test_robots_keeps_crawlers_out_of_presenter_links_and_uploads(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /present/", body)
        self.assertIn("Disallow: /media/", body)


class RenderTests(TestCase):
    def content(self, **fields):
        start = timezone.now()
        data = dict(label="Weekly meeting", starts_at=start, ends_at=start + timedelta(hours=1),
                    place="Google Meet", place_detail="Virtual", icon="video",
                    link="https://discord.gg/kdudev", **FILLED)
        data.update(fields)
        return PosterContent(**data)

    def draw(self, **fields):
        return Image.open(io.BytesIO(render(self.content(**fields),
                                            Image.new("RGB", (800, 1200), "grey"))))

    def test_an_a4_poster(self):
        poster = self.draw()
        self.assertEqual((poster.format, poster.size), ("PNG", (WIDTH, HEIGHT)))

    def test_discord_gets_its_own_mark(self):
        video = self.draw(place="Zoom").crop((770, 1410, 860, 1490))
        discord = self.draw(place="Discord", icon="discord").crop((770, 1410, 860, 1490))
        self.assertNotEqual(video.tobytes(), discord.tobytes())

    def test_text_far_too_long_still_draws(self):
        poster = self.draw(
            title="Supercalifragilisticexpialidocious " * 6,
            summary="word " * 80, about="word " * 90, speaker_name="A" * 50,
            speaker_tag="Professor of Computer Science", icon="pin",
            place="Engineering building, lecture room 301 on the third floor",
            place_detail="Kyungdong University, Goseong campus")
        self.assertEqual(poster.size, (WIDTH, HEIGHT))
