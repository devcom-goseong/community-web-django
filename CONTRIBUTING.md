# Contributing

This is the website of the KDU Developer Community — a student developer
community based at Kyungdong University, South Korea, open to students there
and to any other developer. The site is open source, and help is welcome from
anyone: fixing a bug, improving the writing, making a page easier to use.

You do not need to be a member of the community to contribute.

## Getting it running

`README.md` has the setup: a virtual environment, `pip install -r
requirements-dev.txt`, `manage.py migrate`, `manage.py seed_content` to fill
the database with the site's copy, then `manage.py runserver`. It runs on
SQLite out of the box, so there is nothing else to install.

## How a change gets in

1. Fork the repository and branch from `main`.
2. Make the change, and add or update tests for it.
3. Run the checks locally: `ruff check .` and `python manage.py test`.
4. Open a pull request. Describe what it does and why, in plain English.
5. Wait for a review. Every pull request is read and approved by a maintainer
   before it is merged.

Pull requests are reviewed as soon as there is time. If one has gone quiet for
a week, leave a comment asking about it — that is not rude, it is helpful.

## What runs on your pull request

| Check | What it means |
| --- | --- |
| `1 · Lint` | `ruff` is happy with the formatting and imports. |
| `2 · Django checks` | The settings pass Django's own deployment checks, and no migration is missing. |
| `3 · Test` | The test suite passes against PostgreSQL. |
| `Approved by the maintainer` | A maintainer has approved *these* commits. Pushing more commits afterwards turns it red again, because the new code has not been read yet. |

All four have to be green. Nothing is deployed from a pull request: the build
and deploy stages only ever run on `main`.

## Branches

| Branch | What it is |
| --- | --- |
| `main` | What is live at kdudev.com. Changes arrive by pull request. |
| `staging` | Somewhere to try things out. The checks run; nothing is deployed. |

## Before starting something big

Open an issue and describe the idea first. It saves you building something
that does not fit, and gives other people a chance to help with it.

## House rules for the code

- **Members' details are private.** Anything that decides who can see another
  member goes through `accounts/access.py`, and there are tests covering every
  stage of membership. If a change touches that area, expect those tests to
  have opinions.
- **No secrets in the repository.** Passwords, chat invite links and API keys
  belong in the server's environment, never in a file here.
- **Write the test.** A change in behaviour that no test notices will be sent
  back asking for one.
- **Keep the writing plain.** The site is meant to read like a person wrote it,
  not like documentation. Short sentences, no marketing words, no emoji.
- **Keep the design quiet.** One typeface (PT Sans), soft corners, no capitals
  or letter-spacing for effect. Colours come from the tokens in
  `static/css/variables.css` — add a token rather than a hex value.

## Found a security problem?

Please do not open a public issue for it. Email **devcommunity.global@gmail.com**
with what you found and how to reproduce it, and you will get a reply.
