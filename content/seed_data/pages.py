"""Copy for the prose pages. Imported by seed_content."""

from datetime import date

from content.models import Page, PageSection

PAGES = [
    {
        "slug": "rules", "title": "Community rules", "order": 0,
        "eyebrow": "Rules · Read before applying",
        "lead": "The rules every member of the KDU Developer Community agrees to: behaviour, "
                "taking part, crediting work, use of the platforms, and how breaches are handled.",
        "show_version": True, "version": "Version 2", "reviewed_on": date(2026, 9, 4),
        "notice_title": "Working version",
        "notice_body": "This is the current version. The leadership team will confirm the final "
                       "wording before the community opens to a wider group. If something reads "
                       "wrong to you, say so — that is easier to fix now than later.",
        "intro": "The point of having rules is not to make the community strict. It is to avoid "
                 "confusion later, so everyone knows what is expected of them and what they can "
                 "expect from everyone else. Applying to join means agreeing to these.",
        "sections": [
            ("behaviour", "1. General behaviour", "",
             "Treat every member with respect, in every channel and every meeting.\n"
             "No harassment, no discrimination, no abuse. This one is not negotiable.\n"
             "Disagree with the argument, not the person.\n"
             "Keep communication professional and appropriate."),
            ("taking-part", "2. Taking part", "",
             "Respect meetings and activities. Turn up when you said you would, and say early when you cannot.\n"
             "Do not spam the channels.\n"
             "Keep discussion relevant to the channel it is in.\n"
             "Ask questions freely. Nobody here is judged for not knowing something."),
            ("work", "3. Projects and credit", "",
             "Respect the work other members have done.\n"
             "Credit what you use — code, designs, writing, data, anything.\n"
             "Never present work that is not yours as your own.\n"
             "Agree who is responsible for what at the start of a group project."),
            ("platforms", "4. Communication platforms", "",
             "Use each channel for what it is for.\n"
             "Keep announcements, discussion, project work and casual conversation separate.\n"
             "Post appropriate content only.\n"
             "What a member shares inside the community stays inside it, unless they say otherwise."),
            ("leadership", "5. Leadership and decisions", "",
             "The leadership team is responsible for the rules, the platforms, the activities and the organisation.\n"
             "Decisions are made by the leadership team, and explained when a member asks.\n"
             "Any member can propose an improvement, and proposals are answered either way.\n"
             "Bring problems to the leadership team early rather than letting them grow."),
            ("breaches", "6. If a rule is broken",
             "Most problems are misunderstandings, so the first step is always a conversation. "
             "Beyond that:",
             "A private conversation with someone on the leadership team.\n"
             "A formal warning if it continues.\n"
             "Removal from the community for serious or repeated breaches.\n"
             "Harassment, discrimination, or passing off work that is not yours can mean removal "
             "without the earlier steps."),
            ("changes", "7. Changes to these rules",
             "These are not permanent. As the community grows the leadership team will review them "
             "and improve them where necessary. Members can propose changes at any time, and "
             "anything material will be announced on the community platform before it takes effect.",
             ""),
        ],
    },
    {
        "slug": "terms", "title": "Terms", "order": 1,
        "eyebrow": "Terms · Membership and use",
        "lead": "The terms of membership and of using this website: applying, what we expect from "
                "each other, ownership of work, and what this community is and is not.",
        "show_version": True, "version": "Version 1", "reviewed_on": date(2026, 8, 29),
        "notice_title": "Plain language, not legal advice",
        "notice_body": "These terms are written to be understood by the students who have to "
                       "follow them. They were not drafted by a lawyer. If the community ever "
                       "needs terms that hold up formally, have them reviewed by someone qualified.",
        "sections": [
            ("who", "1. Who we are",
             "The KDU Developer Community is a student-run community based at Kyungdong "
             "University, South Korea, open to students there and to developers outside it. In "
             "these terms, “we” means the leadership team and “you” means a member or an applicant.",
             ""),
            ("applying", "2. Applying and membership", "",
             "Anyone may apply, at any level of experience, technical or not.\n"
             "Applying does not guarantee acceptance. The leadership team reviews every application.\n"
             "The information you give on the form should be accurate.\n"
             "Membership can end if the community rules are broken.\n"
             "You can leave whenever you want, and ask for your details to be deleted."),
            ("expect-you", "3. What we expect from you",
             "That you follow the community rules. They are short, and reading them is part of applying.",
             ""),
            ("expect-us", "4. What you can expect from us",
             "The community is run by students in their own time, alongside their studies. We do "
             "what we say we will, but activities can move, change or be cancelled, and replies "
             "are not instant. If something is not working, tell the leadership team.",
             ""),
            ("work", "5. Ownership of work", "",
             "Anything you make stays yours. Taking part does not transfer ownership to the community.\n"
             "If several members build something together, agree who owns what before you start.\n"
             "Credit work that is not yours, and do not share what you have no right to share."),
            ("site", "6. Using this website",
             "The site is provided as it is. It may be unavailable at times and its content may "
             "change. Do not use the form to send anything unlawful, abusive, or deliberately "
             "misleading.",
             ""),
            ("official", "7. Not a university service",
             "This community is organised by students. It is not an official service of Kyungdong "
             "University and it does not speak for the university. Where an activity depends on "
             "university facilities, that is agreed separately and is not guaranteed by these terms.",
             ""),
            ("changes", "8. Changes",
             "These terms can change as the community grows. The date at the top of this page "
             "shows when they were last reviewed, and anything material will be announced on the "
             "community platform.",
             ""),
        ],
    },
    {
        "slug": "privacy", "title": "Privacy notice", "order": 2,
        "eyebrow": "Privacy · Plainly put",
        "lead": "What the KDU Developer Community collects when you use the form or create an "
                "account, what happens to it, who can see it, and how to have it deleted.",
        "show_version": True, "version": "Version 1", "reviewed_on": date(2026, 8, 29),
        "intro": "This covers this website, the form on it, and member accounts. It is written "
                 "to be read rather than to protect us. If anything here is unclear, ask, "
                 "and we will fix the wording.",
        "sections": [
            ("collect", "1. What we collect", "From the form, only what you type into it:",
             "Whether you are applying to join or asking a question\n"
             "Your name and your email address\n"
             "Whether you are a KDU student, and your student ID if you choose to give it\n"
             "The areas of interest you tick\n"
             "Your message\n"
             "That you agreed to be contacted, and that you accepted the rules, terms and this notice"),
            ("account", "2. If you create an account",
             "An account is optional. You can send the form, apply, and get a reply without "
             "one.\n\n"
             "If you do create one, we additionally hold your password and whether you have "
             "confirmed your email address. The password itself is not stored: what we keep "
             "is a salted hash of it, which cannot be turned back into the password, so "
             "nobody here can read it or tell you what it is. Everything else on your "
             "account — your introduction, your interests, your links — is there because you "
             "typed it, and you can change or empty it yourself at any time.",
             ""),
            ("use", "3. What happens to it",
             "Your submission is sent to the community's own server, where it is stored so the "
             "leadership team can review it, and turned into two emails: a confirmation to you, so "
             "you know it arrived, and a notification to the community inbox.\n\n"
             "The server is run by the community and is not shared with anyone else.",
             ""),
            ("who", "4. Who can see it",
             "The members of the leadership team who have access to the community inbox and the "
             "review screen. Nobody outside the community.",
             ""),
            ("automatic", "5. What happens automatically", "",
             "Your IP address is used briefly, and only in memory, to stop one source flooding the "
             "form. It is not stored and it is not put in either email.\n"
             "Our hosts keep standard server logs, as every web host does.\n"
             "The emails are sent through Gmail, so Google handles them as it handles any email.\n"
             "The typeface loads from Google Fonts, so Google receives your IP address and browser "
             "details when a page opens."),
            ("cookies", "6. Cookies", "",
             "Reading this site sets no cookies at all.\n"
             "Signing in sets two: one that keeps you signed in, and one that stops a form "
             "being submitted from another site. Both are strictly necessary for an account "
             "to work, neither follows you anywhere, and signing out clears the first.\n"
             "There are no analytics, advertising or third-party cookies, which is why there "
             "is no consent banner to click."),
            ("dont", "7. What we do not do", "",
             "No analytics, and no tracking of any kind.\n"
             "No advertising, and no marketing lists.\n"
             "No email from us except the ones you cause: a reply, a confirmation, a link to "
             "confirm your address, or a link to reset your password.\n"
             "Your details are never sold, shared, or passed to anyone outside the leadership team."),
            ("keep", "8. How long we keep it",
             "Your application stays on file for as long as you are a member. If we cannot "
             "accept your application we delete it once we have told you. An account stays "
             "until you ask us to close it, and closing it deletes the account and everything "
             "on it. If you ask us to delete anything at any point, we delete it.",
             ""),
            ("rights", "9. Asking for your data",
             "You can ask for a copy of what we hold about you, ask us to correct it, or ask us to "
             "delete it. Reply to the confirmation email you received, or use the form and say what "
             "you want. We will do it and tell you when it is done.",
             ""),
            ("changes", "10. Changes",
             "If this notice changes we update the date at the top of this page, and announce "
             "anything material on the community platform.",
             ""),
        ],
    },
    {
        "slug": "start", "title": "Your first month", "order": 3,
        "eyebrow": "Getting started · New members",
        "lead": "What actually happens after you are accepted, week by week, and what nobody "
                "expects of you.",
        "intro": "Nobody expects you to contribute anything in your first weeks. The only thing "
                 "that helps is turning up.",
        "sections": [
            ("week-one", "Week one — turn up and listen",
             "Come to the weekly meeting. Say your name and one sentence about what you are "
             "interested in. Then listen. You will not follow all of it, and that is the normal "
             "experience for everyone in their first week, including people who have been "
             "programming for years.", ""),
            ("week-two", "Week two — find a study group",
             "Join one that exists, or say what you want to learn and see if two other people want "
             "to learn it too. This is the fastest way to stop being a stranger, because a study "
             "group is four people who now know your name.", ""),
            ("week-three", "Week three — put your hand up for something",
             "Submit an idea, or join a project that needs a pair of hands. You do not need to be "
             "the person who writes the hardest part. Projects need testing, documentation, design, "
             "and someone who keeps track of what was decided.", ""),
            ("week-four", "Week four — say something at the meeting",
             "Take two minutes in the member updates to say what you learned, what you are "
             "building, or what you are stuck on. Being stuck is a perfectly good update and "
             "usually the most useful one.", ""),
            ("not-expected", "What nobody expects of you", "",
             "To attend everything. Come to what is useful to you.\n"
             "To already be good. Most people here are learning.\n"
             "To have a project. Plenty of members join other people's.\n"
             "To write code at all, if that is not your thing.\n"
             "To know the answer when someone asks you a question."),
            ("stuck", "If you get stuck or go quiet",
             "People disappear from communities quietly and usually for ordinary reasons: exams, "
             "work, losing the thread. If that happens, come back whenever. If something about the "
             "community is what put you off, tell the leadership team.", ""),
        ],
    },
    {
        "slug": "accessibility", "title": "Accessibility", "order": 4,
        "eyebrow": "The site · Accessibility",
        "lead": "What this site does to stay usable, what we know is imperfect, and how to tell us "
                "when something does not work for you.",
        "intro": "A community that says anyone can join should have a website anyone can use. This "
                 "page says what we have actually done, rather than claiming a standard we have "
                 "not been audited against.",
        "sections": [
            ("done", "What the site does", "",
             "Semantic HTML throughout, with one h1 per page and no skipped heading levels.\n"
             "A skip link to jump straight past the navigation.\n"
             "A visible focus outline on every link, button and field.\n"
             "The whole site is operable by keyboard, and the mobile menu closes with Escape.\n"
             "Form fields have real labels, and errors are announced with the field.\n"
             "Errors are shown with a border, an icon and text — never by colour alone.\n"
             "All movement stops entirely when prefers-reduced-motion is set.\n"
             "Images carry width and height so the page does not jump while it loads.\n"
             "Text reflows down to 320px without a horizontal scrollbar."),
            ("limits", "What we know is imperfect", "",
             "The site has not been audited by anyone outside the team, and none of us uses a "
             "screen reader daily.\n"
             "The display face is a book type with fine strokes. If you find it hard to read, tell "
             "us — that is fixable in one file.\n"
             "There is no high-contrast variant.\n"
             "Some pages are long, and the contents lists in the margin are only on wider screens."),
            ("report", "Telling us something is wrong",
             "Use the form and say what happened, what you were using, and what you expected. You "
             "do not need to know the technical cause. An accessibility problem is a bug, it gets "
             "treated as one, and we will tell you what we did about it.", ""),
        ],
    },
    {
        "slug": "contribute", "title": "Help build this site", "order": 5,
        "eyebrow": "The site · Contributing",
        "lead": "This website is open source and is a reasonable first contribution if you have "
                "never worked on someone else's codebase.",
        "intro": "The site you are reading is public, and members are welcome to work on it. For a "
                 "lot of people it is a good first experience of changing code somebody else wrote.",
        "sections": [
            ("repo", "Where it lives",
             "github.com/devcom-goseong/community-web\n\n"
             "The public pages are plain HTML and CSS. The part that receives the form is a small "
             "Django service, with its own README.", ""),
            ("shape", "How it is put together", "",
             "Every colour, size and spacing value is a custom property in css/variables.css.\n"
             "One typeface for the whole site. Hierarchy comes from size, weight and italic.\n"
             "Greyscale only — no accent colour anywhere, including buttons and hover states.\n"
             "Every page works without JavaScript."),
            ("jobs", "Things that need doing", "",
             "The platform links in the footer are placeholders until the invite links exist.\n"
             "The social sharing image is generated by a script using a substitute typeface.\n"
             "Accessibility testing by somebody who actually uses a screen reader.\n"
             "The rules are a working version and need the final wording confirmed.\n"
             "Korean translations, if that turns out to be useful to members."),
            ("proposing", "Proposing a change",
             "Open an issue describing what you want to change before writing much of it, so nobody "
             "duplicates work. Small, focused changes are easier to review than large ones.\n\n"
             "Credit other people's work if you bring anything in from elsewhere. That is in the "
             "rules and it applies to the codebase too.", ""),
        ],
    },
]


def load_pages():
    for spec in PAGES:
        page, _ = Page.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "title": spec["title"],
                "eyebrow": spec.get("eyebrow", ""),
                "lead": spec["lead"],
                "intro": spec.get("intro", ""),
                "notice_title": spec.get("notice_title", ""),
                "notice_body": spec.get("notice_body", ""),
                "show_version": spec.get("show_version", False),
                "version": spec.get("version", "Version 1"),
                "reviewed_on": spec.get("reviewed_on"),
                "order": spec.get("order", 0),
            },
        )
        page.sections.all().delete()
        for index, (anchor, heading, body, bullets) in enumerate(spec["sections"]):
            PageSection.objects.create(
                page=page, anchor=anchor, heading=heading,
                body=body, bullets=bullets, order=index,
            )
