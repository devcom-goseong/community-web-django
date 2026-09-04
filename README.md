# The Django site

A Django app that does two things:

1. **Renders every public page from the database**, so the copy is editable in
   the admin by people who will never open the CSS.
2. **Receives the join / contact form**, stores each application so the
   leadership team can review them in one place, and sends the two emails.

**It is not live yet.** The static Netlify build is still the site visitors
see. This runs alongside it until the team decides to switch over.

```
Netlify (dev-comm.netlify.app)     this app (your VPS)
  the live site, unchanged           the same pages, from the database
                                     /admin/ to edit every word of them
                                     /admin/ to review applications
                                     POST /api/register
```

Both read the same `css/`, `js/` and `assets/` from the repository root, so
there is one copy of the design and not two that drift apart.

## What is editable in the admin

| Screen | What it controls |
| --- | --- |
| Site settings | Community name, university, founding date and the footer text |
| Social links | Every platform the community is on — Facebook, LinkedIn, GitHub, Instagram, X, Discord, WhatsApp, or anything added later. Each one is a row, so adding a platform is a form in the admin rather than a migration. Two groups: **Where we talk** and **Follow us**. Leave an address blank and the site shows a "Soon" badge instead of a dead link; fill it in and it becomes a real link on every page at once |
| Members | Everyone with an account: their status, whether they have confirmed their email address, and what they accepted when they signed up |
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
account is what comes afterwards: it is how somebody signs in, keeps their own
details current, and sees where their application got to.

| Address | What it is |
| --- | --- |
| `/account/sign-up/` | Create an account. Requires accepting the rules, terms and privacy notice, exactly as the join form does |
| `/account/sign-in/` | Sign in with an email address |
| `/account/me/` | A member's own page: their details, their confirmation state, and the applications sent from their address |
| `/account/verify/<token>/` | Confirms an address from the link in the welcome email |
| `/account/password/reset/` | Django's password reset, using this site's templates and the same SMTP account |

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

Sign-up shares the join form's rate limiter but not its budget: the limiter
takes a `scope`, so the two cannot starve each other on a shared university
connection.

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

Twenty-seven tests. Sixteen cover the form endpoint: validation, the required agreement, the
honeypot, the timing trap, rate limiting, CR/LF stripping from mail headers,
HTML escaping, the no-JavaScript path, and that an application survives an
email outage. One test asserts the submitter's IP is never written to the
database, because the privacy notice says so and a promise in prose is worth
less than a test.

The other eleven cover the content: every page renders from the database, every
activity has a page, unpublishing something removes it from the site *and*
returns a 404, editing a section changes the rendered page, filling in a
platform URL turns the "Soon" tag into a link, and re-running the seed does not
duplicate anything.

---

## Deploying to a VPS

### Once, on the server

1. Install Docker and the compose plugin.
2. Point a DNS A record at the box, for example `apply.your-domain`.
3. Create a directory, and put three things in it:
   - `docker-compose.prod.yml`
   - `nginx/templates/default.conf.template`
   - `.env` (from `.env.example`, filled in — `APP_HOST` must match the DNS name)
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

6. Create the first admin user:

   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
   ```

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
| `accounts/models.py` | `Member`, the community-facing half of an account |
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
