# Contributing

Thanks for wanting to help. This is the website of a student developer
community, and contributions are welcome from anyone.

## How a change gets in

1. **Fork the repository** and make a branch from `main`.
2. **Open a pull request.** Say what the change does and why, in plain English.
3. **Wait for a review.** Every pull request is read and approved by the
   maintainer before it is merged. Nothing is merged without that.

Pull requests are reviewed as soon as there is time for them. If one has gone
quiet for a week, it is fine to leave a comment asking.

## What the checks do

Two things run on every pull request, and both have to pass:

| Check | What it means |
| --- | --- |
| **1–3 Lint / Django checks / Test** | The code is formatted, the settings are sound and the tests pass. Run them yourself first: see the Tests section of README.md. |
| **Approved by the maintainer** | The maintainer has approved *these* commits. Pushing a new commit after an approval turns it red again, because the new code has not been looked at. |

The build and deploy stages only ever run on `main`, so a pull request can
never reach the live site on its own.

## Branches

| Branch | For what |
| --- | --- |
| `main` | What is live at kdudev.com. Protected: changes come in by pull request. |
| `staging` | Somewhere to try things. The checks run; nothing is deployed. |

## Before you start something big

Open an issue first and describe the idea. It saves you building something that
does not fit, and gives other people a chance to help with it.

## Things to keep in mind

- **Keep people's details private.** Anything that shows a member to anyone
  else goes through `accounts/access.py`, and there are tests covering who can
  see what. If a change touches that, the tests will tell you.
- **Do not put secrets in the repository.** Passwords, invite links and API
  keys belong in the server's environment, never in a file here.
- **Write the tests.** A change to behaviour that no test notices will be
  asked for one.

---

## For the repository owner: making the review a rule

The approval check above reports, but it cannot stop a merge on its own. Only
the owner of this repository (`devcom-goseong`) can make it binding, and it
takes a minute:

**Settings → Branches → Add branch protection rule** (or **Settings → Rules →
Rulesets** for the newer screen), for the branch `main`:

- ☑ **Require a pull request before merging**
  - Required approvals: **1**
  - ☑ Dismiss stale pull request approvals when new commits are pushed
  - ☑ Require review from Code Owners  *(`.github/CODEOWNERS` points at the maintainer)*
- ☑ **Require status checks to pass before merging**
  - ☑ Require branches to be up to date before merging
  - Select: `1 · Lint`, `2 · Django checks`, `3 · Test`, `Approved by the maintainer`
- ☑ **Block force pushes**
- ☑ **Restrict deletions**

Two things worth knowing before switching it on:

- It stops **everyone**, including whoever is used to committing to `main`
  straight from the GitHub web page. That is the point, but it is a change of
  habit. Admins can still bypass unless *Do not allow bypassing the above
  settings* is ticked.
- GitHub does not let anyone approve their own pull request. If the maintainer
  is the only reviewer, their own pull requests cannot be approved by anyone —
  either leave the admin bypass available for them, or add a second reviewer.

To let the maintainer manage this directly, change their repository access from
**Write** to **Admin** under **Settings → Collaborators**.
