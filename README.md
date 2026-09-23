# The Django site

A Django app that does four things:

1. **Renders every public page from the database**, so the copy is editable in
   the admin by people who will never open the CSS.
2. **Receives the join / contact form**, stores each application so the
   leadership team can review them in one place, and sends the two emails.
3. **Runs member accounts**: sign-up, a members directory, profiles people can
   share, and the community's invite links, shown only to approved members.
4. **Runs events**: sign-up with places and a waiting list, calendar files,
   reminders the day before, and attendance that shows up on profiles.

**It is not live yet.** The static Netlify build is still the site visitors
see. This runs alongside it until the team decides to switch over.

```
Netlify (dev-comm.netlify.app)     this app (your VPS)
  the live site, unchanged           the same pages, from the database
                                     /admin/ to edit every word of them
                                     /admin/ to review applications
                                     POST /api/register
```

The stylesheets, scripts and images in `static/` began as copies of the static
site's. `static/css/members.css` exists only here, because only this app has
member pages; the other stylesheets should be changed in the static site's
repository first and copied across, so the two front ends do not drift apart.

## What is editable in the admin

| Screen | What it controls |
| --- | --- |
| Site settings | Community name, university, founding date and the footer text |
| Social links | Every platform the community is on — Facebook, LinkedIn, GitHub, Instagram, X, Discord, WhatsApp, or anything added later. Each one is a row, so adding a platform is a form in the admin rather than a migration. Two groups: **Where we talk** and **Follow us**. Leave an address blank and the site shows a "Soon" badge instead of a dead link. **Members only** is ticked by default: the address is then only ever sent to approved members who are signed in, and everyone else sees the name with a "Members" badge. Untick it only for public pages people can follow |
| Members | Everyone with an account: status, email confirmation, profile visibility, their projects, and what they accepted when they signed up. Approve, pause, remove and hide-profile are actions on the list |
| Events | Title, time, place, online link, capacity, who can see it and who can register. The registrations are listed on each event, with role and attendance editable. Actions: publish, cancel and notify everyone, mark attendance, export attendees |
| Registrations | Every sign-up across all events, for marking attendance and roles in bulk |
| Pages | The rules, terms, privacy notice, first month, accessibility and contributing pages — each with its own sections, which also build the contents list in the margin |
| Activities | All seven, with their cadence tags, index copy and the sections on their own pages |
| Home page cards and facts | The four cards and the at-a-glance strip |
| Values | What the community holds members to |
| Areas of responsibility | How the work is divided, described without naming anyone |
| Joining steps | The four steps on the About page |
| Questions | The FAQ |
| Interest areas | Both the explanations *and* the tick boxes on the application form |
| Resources | Grouped links, each with a note |

Everything has a **published** tick and an **order** number, so any of it can be
hidden or reordered without a deploy.

Run `python manage.py seed_content` once to load the site's current copy into
the database. It is idempotent, but it overwrites the rows it manages — so run
it at setup, and edit in the admin after that.

---

## Member accounts

Anyone can use the join form without an account — that has not changed. An
account is what comes afterwards: it is how somebody gets into the community's
chats, finds people to build with, signs up for events and keeps a profile.

| Address | What it is |
| --- | --- |
| `/account/sign-up/` | Create an account. Requires accepting the rules, terms and privacy notice, exactly as the join form does |
| `/account/sign-in/` | Sign in with an email address |
| `/account/me/` | A member's own page: where they are on the way in, the invite links once approved, their events, their profile |
| `/account/profile/` | Edit the profile: name, address, who can see it, introduction, interests, links, projects |
| `/account/close/` | Close the account. Deletes everything on it, after asking for the password |
| `/account/verify/<token>/` | Confirms an address from the link in the welcome email |
| `/account/password/reset/` | Django's password reset, using this site's templates and the same SMTP account |
| `/members/` | The members directory. Approved members and the leadership team only |
| `/members/<handle>/` | A profile |
| `/events/` | Upcoming and recent events |
| `/events/<slug>/` | An event: register, cancel, add to calendar |

### Who can see what

Everything below is decided in one place, `accounts/access.py`, and tested as a
matrix in `accounts/test_members.py` and `events/tests.py`.

| | Visitor | Signed up, email not confirmed | Awaiting review | Approved member | Leadership team |
| --- | --- | --- | --- | --- | --- |
| Invite links (Discord, WhatsApp) | no | no | no | **yes** | yes |
| Members directory | no | no | no | **yes** | yes |
| Profile set to "Only me" | no | no | no | no (owner yes) | yes |
| Profile set to "Members" | no | no | no | **yes** | yes |
| Profile set to "Anyone with the link" | **yes** | yes | yes | yes | yes |
| Events marked "members only" | no | no | no | **yes** | yes |
| Register for an event open to members | no | no | no | **yes** | only with a member account of their own |
| Register for an event open to any confirmed account | no | no | **yes** | yes | only with a member account of their own |
| An event's online call link | only people who have a place at that event |||||

A paused or removed member loses all of it at once, and their profile
disappears for everyone else whatever it was set to. Anything a person may not
see is answered with the same "not available" page whether it exists or not, so
the site cannot be used to discover which members-only events or profiles exist.

### Approving people

- **From the Members list:** select people, choose *Approve as members*. They get
  an email saying they are in. The email does not contain the invite links —
  emails get forwarded — it sends them to their account page, where the links are.
- **By accepting an application:** *Mark as accepted* on an application also
  approves a matching account with a confirmed email address.
- **Applied first, signed up later:** an account whose address matches an
  accepted application is approved automatically when its owner confirms the
  address. Only on confirmation, or anyone could sign up with an accepted
  applicant's email and inherit the approval.
- **Pausing or removing** someone gives up the event places they held, and the
  waiting list moves up. Removing also sets their profile back to hidden.

Change a member's status with the actions or the Members edit page, never
anywhere else: those are what send the emails and move the waiting lists.

### Invite links

- Tick **Members only** for any invite link. It is ticked by default, so a new
  chat platform added in a hurry is private until someone decides otherwise.
- Make Discord invites **never expire** (Discord's default is seven days), or
  the link on the account page will quietly stop working.
- If an invite link leaks, make a new one on the platform, revoke the old one
  there, and paste the new one into the admin. It changes everywhere at once.
- Never put an invite link in the static Netlify site's HTML. Anything there is
  public. There is a comment in its footer saying so.

### Profiles and the directory

- **Private by default.** Nobody appears in the directory until they choose to.
  Accounts created before profiles existed were all set to hidden.
- **Never shown:** email address, student ID, or whether someone is a student.
- **Profile addresses** (`/members/sam-park/`) are generated from the name. A name
  with no Latin letters, such as 김민수, gets a neutral one like `member-3fa9c1`,
  because a Korean name produces an empty web address otherwise. Members can
  change it; some words, like `admin` and `me`, are reserved.
- **Links** must be http or https, and the GitHub and LinkedIn fields must point
  at those sites, so a profile cannot be used to host a link to anything.
- **Not indexed.** Every profile page asks search engines not to index it, and
  `robots.txt` keeps crawlers out of `/members/` and `/account/`.
- **Moderation:** *Hide profile* on the Members list takes a profile down without
  touching the membership. The projects a member lists are editable on their
  admin page.

### Events

- **Places and the waiting list.** When an event is full, sign-ups join a waiting
  list. When someone with a place cancels — or is paused, or deletes their
  account — the first person waiting gets the place and an email. Nobody can
  jump the list, and two people cannot take the last place at the same moment:
  every change locks the event row first.
- **Raising the capacity** in the admin moves the waiting list up as soon as you
  save.
- **Cancel, do not delete.** *Cancel and notify everyone who signed up* emails
  them all. An event with registrations cannot be deleted at all, because that
  would erase attendance from people's profiles.
- **Attendance** is marked after the event: *Mark everyone with a place as
  attended* on the events list, then untick anyone who did not come. Only
  attended events appear on profiles, with the role (presented, organised, helped).
- **Exports** open cleanly in Excel, Korean names included, and anything a member
  typed that a spreadsheet would run as a formula is neutralised.
- **Times** are entered and shown in Korean time, always labelled KST. Calendar
  files use UTC, so they land at the right local time for anyone, anywhere.

### Reminders

`python manage.py send_event_reminders` emails everyone with a place at an event
starting within `EVENT_REMINDER_HOURS` (24 by default). In production the
`scheduler` service in `docker-compose.prod.yml` runs it every hour. It is safe
to run twice at once, retries anything that failed to send on the next run, and
does not remind someone who only signed up inside the window.

**Gmail's sending limit** is about 500 messages a day for an ordinary account.
Confirmations, waiting-list emails, reminders and cancellations all count. A
large event cancelled on a busy day could reach it; if the community grows past
that, move email to a transactional provider — it is one setting.

Four decisions worth knowing about:

- **Email is the identity.** `User.username` is set to the address so the stock
  admin and password reset keep working, and `accounts/backends.py` does the
  sign-in lookup case-insensitively, because nobody types their address the
  same way twice.
- **`auth.User` was kept, not replaced.** Swapping `AUTH_USER_MODEL` after the
  first migration is a rewrite rather than a change, so everything the
  community needs beyond the stock model lives on `Member`, a one-to-one row.
- **Confirmation links are signed, not stored.** `django.core.signing` with a
  three-day window: nothing to expire by hand, nothing to clean up, and a link
  that has already been used still works, which is what someone who clicks
  twice expects. The address is inside the signed payload and checked at the
  point of use, so a link issued for an address that has since changed does not
  silently confirm the new one.
- **An account is not membership.** A new account is `Awaiting review` until
  somebody on the leadership team approves it in the admin.

Every form shares one rate limiter, `config/ratelimit.py`, with a separate
allowance per form so they cannot starve each other on a shared university
connection. It trusts the address nginx saw (`X-Real-IP`), not the first entry
of `X-Forwarded-For`: that entry is written by the client, and an earlier
version that read it could be bypassed by sending a made-up header.

---

## Marketing pitches are refused

The join form is for people who want to join or ask something. Cold outreach —
offers to improve the site's Google ranking, sell backlinks, redesign the site,
run ads — is refused outright: nothing is stored, nobody is emailed, and the
sender is told plainly that it was not submitted.

`applications/spam.py` holds the list. It matches on whole words after folding
accents and turning punctuation into spaces, so "S.E.O.", "S E O" and "SEO" all
count, while "museology" and "roads" do not. Only the name and the message are
checked — not the email address, because someone with an agency address may
still be a real student, and not the interest tick boxes.

Two environment variables tune it without touching the code:

| Variable | What it does |
| --- | --- |
| `EXTRA_BLOCKED_TERMS` | More terms to refuse, comma separated |
| `UNBLOCKED_TERMS` | Terms from the built-in list to allow again |

`UNBLOCKED_TERMS` matters more than it looks. Some entries are deliberately
blunt because that is what was asked for, and they will also turn away a
genuine member:

- **seo** — refuses "I want to learn SEO".
- **digital marketing**, **email marketing**, **social media marketing** —
  refuse a student who says that is what they are interested in.

If that happens, put the word in `UNBLOCKED_TERMS`. The longer phrases
("seo services", "marketing agency", "i came across your website") keep working,
and those are what the real pitches say. Refusals are logged with the term that
matched — `journalctl -u kdu.service | grep "refused a submission"` — so it is
easy to see what is being turned away and whether the list is too keen.

The account sign-up form is not filtered this way; it has its own honeypot and
timing check, and an account on its own gives nobody anything.

---

## Read this before you switch the form over

The published privacy notice currently says, in section 2:

> There is no database. This website does not have one, and your details are
> not written anywhere except those two emails.

**That stops being true the moment this service goes live**, because the whole
point of it is a database. Publishing a privacy notice that misdescribes what
you do with people's data is not a small thing, and it is the one part of this
change that cannot be left until later.

Section 2 of `privacy.html` has to be rewritten in the same commit that points
the form at this service. Suggested replacement:

> **2. What happens to it**
>
> Your submission is sent to the community's own server, where it is stored so
> the leadership team can review it, and turned into two emails: a confirmation
> to you, so you know it arrived, and a notification to the community inbox.
>
> The server is run by the community and is not shared with anyone else. Your
> IP address is still not stored — it is used only, and briefly, to stop one
> source flooding the form.

Section 6, on how long things are kept, is already accurate. Section 4 needs
"our host, Netlify" widened to mention the community server as well.

Accounts add one more: `privacy.html` says the site "sets no cookies for
visitors and stores nothing in your browser". Signing in sets a session cookie
and a CSRF cookie, so that sentence has to go at the same time.

The copy **in this repository** has already been rewritten — it has a section
on accounts, a section on cookies, and says plainly that the password is stored
as a salted hash and cannot be read back. Run `python manage.py seed_content`
and read `/privacy/` to see it. What still needs doing is the copy on the
static Netlify site, which is a different file in a different repository.

---

## Running it locally

```bash
cp .env.example .env          # fill in at least DJANGO_SECRET_KEY
docker compose up --build
docker compose exec web python manage.py createsuperuser
```

Then <http://localhost:8000/admin/>. Email is written to the console in
development, so nothing is sent while you work.

Without Docker:

```bash
python -m venv .venv && . .venv/bin/activate    # .venv\Scripts\activate on Windows
pip install -r requirements-dev.txt
export DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

SQLite is used when `DATABASE_URL` is unset, so it starts with no services
running.

## Tests

```bash
python manage.py test
ruff check .
python manage.py check --deploy --fail-level WARNING
```

About 150 tests, which run in a few seconds.

- **The form endpoint:** validation, the required agreement, the honeypot, the
  timing trap, refusing marketing pitches (ten real pitch shapes, punctuation
  and capitals, a pitch hidden in the name, and eight genuine messages that
  must still go through), rate limiting, CR/LF stripping from mail headers, HTML escaping,
  the no-JavaScript path, and that an application survives an email outage. One
  test asserts the submitter's IP is never written to the database, because the
  privacy notice says so and a promise in prose is worth less than a test.
- **Accounts and members:** who can see invite links, the directory and each
  profile setting, run as a matrix over every stage of membership; that email
  addresses and student details never appear; handles, including Korean names;
  link validation; approving, pausing and removing; accepted applicants being
  approved only after confirming; and closing an account.
- **Events:** who can see and register for what; places, the waiting list and
  its order; nobody jumping the queue; places freed by pausing or deleting an
  account; the online link staying private; cancelling and notifying; calendar
  files, including folding Korean text; the spreadsheet export; and the
  reminder job sending once, skipping what it should and retrying failures.
- **The rate limiter:** that a made-up `X-Forwarded-For` header does not reset it.
- **The content:** every page renders from the database, unpublishing removes a
  page and returns a 404, and re-running the seed does not duplicate anything.

Tests use a fast password hasher; nothing outside `manage.py test` does.

---

## Deploying to a VPS

### Once, on the server

1. Install Docker and the compose plugin.
2. Point a DNS A record at the box, for example `apply.your-domain`.
3. Create a directory, and put three things in it:
   - `docker-compose.prod.yml`
   - `nginx/templates/default.conf.template`
   - `.env` (from `.env.example`, filled in — `APP_HOST` must match the DNS name,
     and `APP_URL` must be `https://` plus that name, or links in reminder
     emails will be wrong; `check --deploy` warns about it)
4. Issue the certificate **before** starting nginx, because the config
   references files that do not exist yet:

   ```bash
   docker compose -f docker-compose.prod.yml up -d web db
   docker run --rm \
     -v certbot-conf:/etc/letsencrypt -v certbot-www:/var/www/certbot \
     -p 80:80 certbot/certbot certonly --standalone \
     -d apply.your-domain --agree-tos -m you@example.com --no-eff-email
   docker compose -f docker-compose.prod.yml up -d
   ```

5. Reload nginx after each renewal. Certbot renews in its own container but
   cannot reload nginx, so add a cron entry:

   ```
   0 4 * * * cd /path/to/app && docker compose -f docker-compose.prod.yml exec -T nginx nginx -s reload
   ```

6. Create the first admin user, and load the site's copy:

   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   docker compose -f docker-compose.prod.yml exec web python manage.py seed_content
   ```

7. The `scheduler` service starts with everything else and sends event
   reminders hourly. Check it is running with
   `docker compose -f docker-compose.prod.yml logs scheduler` — each run prints
   one line saying how many reminders went out.

### Continuous deployment

`.github/workflows/ci.yml` runs on every push and pull request:

1. **Lint and test** against a real Postgres, including `check --deploy` and a
   check that no model change is missing a migration.
2. **Collect static files**, which proves the asset pipeline before the image
   is built rather than after.
3. **Build and publish** the image to
   `ghcr.io/devcom-goseong/community-web-django`, tagged `latest` and by commit
   SHA.
4. **Deploy** over SSH: pull, `up -d`, prune, then poll `/healthz` ten times
   and fail the run if the service does not come back.

The deploy job **skips cleanly until the secrets exist**, so the workflow is
green from the first push rather than red until somebody buys a server. Set
these in Settings → Secrets and variables → Actions:

| Secret | What it is |
| --- | --- |
| `VPS_HOST` | Hostname or IP of the server |
| `VPS_USER` | SSH user |
| `VPS_SSH_KEY` | Private key for that user. Use a key made for this, not a personal one |
| `VPS_APP_DIR` | Directory on the server holding `docker-compose.prod.yml` |
| `VPS_PORT` | Optional, defaults to 22 |
| `APP_HOST` | Public hostname, used for the post-deploy health check |

The image is public on GHCR by default. If you make it private, the server
needs its own read token for `docker login`.

---

## Pointing the form at this service

Do this **last**, after a real submission has worked through the admin, and in
the same commit as the privacy notice change above.

The tidiest option keeps the browser on one origin, so no CORS and no change to
the site's content security policy. In the root `netlify.toml`, replace the
function redirect with a proxy:

```toml
[[redirects]]
  from = "/api/register"
  to = "https://apply.your-domain/api/register"
  status = 200
  force = true
```

The form keeps posting to `/api/register` and never knows. Once that is live
and proven, `netlify/functions/register.js` can be deleted.

If you would rather post directly to this service instead, the app already
allows the Netlify origin through `PUBLIC_SITE_ORIGINS`, but you must then also
add that origin to `connect-src` in the site's content security policy or the
browser will block the request.

---

## How it is put together

| Path | What it does |
| --- | --- |
| `config/settings.py` | All configuration, from environment variables |
| `applications/models.py` | The `Application` record, and the review workflow |
| `applications/views.py` | `POST /api/register`, answering in the shape the existing front end already expects |
| `applications/emails.py` | Both messages, over a single SMTP connection |
| `applications/admin.py` | The review screen: filters, search, bulk accept/decline |
| `accounts/models.py` | `Member`, the community-facing half of an account, and `MemberProject` |
| `accounts/access.py` | Who may see what. Every member page asks this |
| `accounts/services.py` | Status changes and their consequences; approving accepted applicants |
| `accounts/validators.py` | Profile addresses, and the rules for links on profiles |
| `accounts/checks.py` | Deployment checks, including one that catches a localhost `APP_URL` |
| `events/models.py` | `Event` and `Registration` |
| `events/services.py` | Registering, cancelling and the waiting list, under a row lock |
| `events/ics.py` | Calendar files |
| `events/management/commands/send_event_reminders.py` | The reminder job |
| `content/context_processors.py` | Where members-only invite links are withheld, for every page |
| `config/ratelimit.py` | The shared rate limiter |
| `accounts/backends.py` | Signing in with an email address rather than a username |
| `accounts/forms.py` | Sign-up, sign-in and profile forms, in the site's own markup |
| `accounts/emails.py` | The welcome email and the signed confirmation link |
| `content/models.py` | Every editable piece of the site, including `SocialLink` |
| `content/seed_data/` | The starting copy. Data modules, not commands — they used to sit in `management/commands/`, where Django listed them as commands that crashed when run |

Two decisions worth knowing about:

- **The IP address is never stored.** The rate limiter hashes it into the cache
  and nothing else touches it, because the privacy notice makes that promise.
- **The application is saved before the emails are attempted.** A mail outage
  costs you a notification, never an applicant — and the admin shows which of
  the two messages actually went out.

The response shape is deliberately identical to the Netlify function's, so the
front end needed no changes at all: `{"ok": true}` on success, and
`{"ok": false, "message": ..., "fields": [...]}` on a rejection.
