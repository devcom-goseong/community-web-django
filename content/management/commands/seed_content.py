"""Load the site's current copy into the database.

Idempotent: run it as often as you like. It matches on slug or title and
updates in place, so it will not create duplicates, but it *will* overwrite
edits made in the admin for the rows it manages. Run it once when setting up,
and after that edit in the admin instead.

    python manage.py seed_content
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import (
    Activity,
    ActivitySection,
    Fact,
    FaqEntry,
    HomeCard,
    InterestArea,
    JoinStep,
    Resource,
    ResourceGroup,
    ResponsibilityArea,
    SiteSettings,
    Value,
)

FACTS = [
    ("Founded", "August 2026"),
    ("Based at", "Kyungdong University"),
    ("Open to", "Students & developers"),
    ("We meet", "Weekly & monthly"),
]

CARDS = [
    ("Learn together", "book",
     "A weekly meeting with one topic, plus member-run study groups for programming, "
     "data science, web, mobile and certification prep. Asking a basic question is normal here."),
    ("Build real things", "brackets",
     "Submit an idea, find people whose skills complete yours, and ship something that exists "
     "outside a tutorial. Teams need designers and writers as much as they need engineers."),
    ("Meet people", "network",
     "One in-person meetup every month for workshops, hands-on sessions and plain conversation, "
     "alongside guest speakers invited into the weekly discussion."),
    ("Show your work", "screen",
     "Demo days give you a room, an audience and honest feedback — practice at presenting, a "
     "portfolio piece, and often a collaborator you did not know you needed."),
]

VALUES = [
    ("Respect first",
     "No harassment, no discrimination, no manufactured conflict. Communication stays "
     "professional even when people disagree."),
    ("Questions are not embarrassing",
     "Nobody should be afraid of being judged for asking something basic. A community where "
     "people stay quiet to look competent is worth nothing."),
    ("Credit is not optional",
     "Respect other people's work. Attribute what you use. Never present someone else's work "
     "as your own."),
    ("Say who is doing what",
     "Group projects need clear responsibilities from the start. Most collapses are not "
     "technical failures, they are unowned tasks."),
    ("Keep the channels clean",
     "Announcements, discussions, project work and casual conversation live in separate places. "
     "Keeping them separate is how a community stays readable."),
    ("Leadership is a responsibility",
     "It is not a title. It means taking something on when it needs doing. The community only "
     "continues if people are willing to contribute and take initiative."),
]

AREAS = [
    ("Rules & structure", "Rules · reports · coordination",
     "Preparing the rules and regulations\n"
     "Keeping decisions written down so they are not lost\n"
     "Coordinating the overall organisation and community structure\n"
     "Keeping the agreed milestones on track"),
    ("Website & identity", "Site · logo · presentation",
     "Building and maintaining the community website\n"
     "Developing the logo and the visual identity\n"
     "The technical side of the community's online presence\n"
     "Keeping what is published accurate as things change"),
    ("Platforms & channels", "Channels · documentation",
     "Designing and documenting the Discord and WhatsApp structure\n"
     "Organising channels and categories that still work as the community grows\n"
     "Supporting communication and documentation across the community"),
    ("Activities & events", "Meetings · study groups · projects",
     "Running the weekly meeting and finding people to moderate it\n"
     "Helping members start and keep study groups going\n"
     "Reviewing submitted ideas and deciding which become projects\n"
     "Organising the monthly in-person meetup and the demo day"),
]

STEPS = [
    ("You apply", "Fill in the form: who you are, what you are interested in, and why you want to join."),
    ("We read it", "Someone on the leadership team reviews it. Applications are read by a person, not filtered by a script."),
    ("You get an invitation", "Accepted members receive an invitation to the community platform and the channels that suit them."),
    ("You take part", "Come to a meeting, join a study group, submit an idea, or just listen for a while first."),
]

FAQS = [
    ("Do I have to be a KDU student?",
     "No. The community is based at Kyungdong University and was started by students there, but "
     "it is open to any other developer who wants to take part. If you are not at the university "
     "you can do everything except the in-person meetups, which happen in Goseong."),
    ("Do I need to know how to code?",
     "No. Real projects need designers, writers, people who understand data, people who organise, "
     "and people who think about who the thing is for. If none of that sounds like you either, "
     "come anyway and find out what does."),
    ("What if I am a complete beginner?",
     "Then you are in the majority. The rules have a line about this because it matters: nobody is "
     "judged for asking a basic question, and anyone who makes you feel stupid for asking is the "
     "one with the problem."),
    ("What if I am already working and experienced?",
     "You are very welcome, and you will get the most out of the projects, the hackathons and demo "
     "day. Be aware that a lot of people here are early on, and that the most valuable thing you "
     "can do is answer questions patiently."),
    ("How much time does it take?",
     "One meeting a week is the baseline. A study group adds an hour or two. A project takes "
     "whatever you agree to give it. Nobody tracks attendance, and it is normal for people to be "
     "more involved in some months than others."),
    ("Is there a fee?", "No. There is no membership fee and nothing is sold to members."),
    ("What happens after I apply?",
     "You get an automatic confirmation email immediately. After that a person on the leadership "
     "team reads what you wrote and replies. If you are accepted you get an invitation to the "
     "community platform and the channels that suit your interests."),
    ("What if my idea gets turned down?",
     "It happens, and it is not held against you. Ideas are reviewed against whether they are "
     "realistic, whether we have people for them, and whether they can be finished. A no comes "
     "with a reason."),
    ("Can I leave?",
     "At any time, without explaining yourself. You can also ask us to delete your details and we will."),
]

INTERESTS = [
    ("Programming", "Any language, any level",
     "Study groups working through fundamentals, or a specific language\n"
     "Writing the code on project teams\n"
     "Hackathons, where it is the most obviously needed skill\n"
     "Answering the questions you were asking six months ago"),
    ("Design", "Interface, visual, product",
     "Deciding how a project looks and how it behaves\n"
     "The identity work — logos, posters, the way the community presents itself\n"
     "Making other people's projects usable by someone who did not build them\n"
     "Perpetually in demand, because most teams here start with engineers only"),
    ("AI & data", "Models, analysis, the useful kind",
     "A recurring weekly meeting topic, at every level from curious to competent\n"
     "Study groups on data science and machine learning\n"
     "The part of a project that needs someone who understands what the numbers mean\n"
     "Competitions and challenges"),
    ("Web & mobile", "Things people can open",
     "Building the things members actually ship\n"
     "This website, which is open source and can be contributed to\n"
     "Study groups on front-end, back-end and mobile frameworks\n"
     "The quickest area to have something finished and demonstrable"),
    ("Writing & documentation", "Making work legible",
     "Documentation that a stranger can follow\n"
     "Writing up what the community decided, so it is not lost\n"
     "Helping teams describe what they built before demo day\n"
     "Deeply undervalued and the reason some projects survive"),
    ("Organising & events", "Making things happen",
     "Running the weekly meeting as moderator\n"
     "Arranging the monthly meetup and the guest speakers\n"
     "Keeping projects on track and responsibilities clear\n"
     "No technical background required, and the community does not run without it"),
    ("Business & outreach", "Who it is for",
     "Working out who a project is actually for\n"
     "Talking to people outside the community — other clubs, companies, speakers\n"
     "The social media presence\n"
     "Turning a working prototype into something people hear about"),
]

RESOURCE_GROUPS = [
    ("How the community actually shares resources", "",
     "Most of it happens in the study groups and the channels, where somebody recommends the "
     "thing that just worked for them. That is more useful than any fixed list, because it comes "
     "with a person you can ask about it. Treat the list below as a way in, not as the material.",
     []),
    ("Programming from the beginning", "", "", [
        ("freeCodeCamp", "https://www.freecodecamp.org/", "Free, structured, project-based, and enormous."),
        ("CS50x", "https://cs50.harvard.edu/x/", "Harvard's introduction to computer science. Hard, and worth it for the foundations."),
        ("The Odin Project", "https://www.theodinproject.com/", "A full path into web development that expects you to build things."),
    ]),
    ("Web and mobile", "", "", [
        ("MDN Web Docs", "https://developer.mozilla.org/", "The reference for HTML, CSS and JavaScript. The thing you will have open every day."),
        ("roadmap.sh", "https://roadmap.sh/", "Useful for seeing what a field contains. Do not treat the roadmaps as checklists."),
    ]),
    ("AI and data", "", "", [
        ("Kaggle Learn", "https://www.kaggle.com/learn", "Short, practical, and connected to datasets and competitions you can enter."),
        ("Microsoft Learn", "https://learn.microsoft.com/training/", "Solid free training, including cloud and AI paths that lead to certifications."),
    ]),
    ("Design", "", "", [
        ("Figma's resource library", "https://www.figma.com/resource-library/", "Design fundamentals written for people who are not designers yet."),
    ]),
]


class Command(BaseCommand):
    help = "Load the site's current copy into the database. Safe to re-run."

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true", help="Only report the totals.")

    @transaction.atomic
    def handle(self, *args, **options):
        loud = not options["quiet"]
        counts = {}

        SiteSettings.get()
        counts["site settings"] = 1

        for index, (label, value) in enumerate(FACTS):
            Fact.objects.update_or_create(label=label, defaults={"value": value, "order": index})
        counts["facts"] = len(FACTS)

        for index, (title, icon, body) in enumerate(CARDS):
            HomeCard.objects.update_or_create(
                title=title, defaults={"icon": icon, "body": body, "order": index})
        counts["home cards"] = len(CARDS)

        for index, (title, body) in enumerate(VALUES):
            Value.objects.update_or_create(title=title, defaults={"body": body, "order": index})
        counts["values"] = len(VALUES)

        for index, (name, subtitle, bullets) in enumerate(AREAS):
            ResponsibilityArea.objects.update_or_create(
                name=name, defaults={"subtitle": subtitle, "bullets": bullets, "order": index})
        counts["areas of responsibility"] = len(AREAS)

        for index, (title, body) in enumerate(STEPS):
            JoinStep.objects.update_or_create(title=title, defaults={"body": body, "order": index})
        counts["joining steps"] = len(STEPS)

        for index, (question, answer) in enumerate(FAQS):
            FaqEntry.objects.update_or_create(
                question=question, defaults={"answer": answer, "order": index})
        counts["questions"] = len(FAQS)

        for index, (name, subtitle, bullets) in enumerate(INTERESTS):
            InterestArea.objects.update_or_create(
                name=name, defaults={"subtitle": subtitle, "bullets": bullets, "order": index})
        counts["interest areas"] = len(INTERESTS)

        links = 0
        for index, (heading, _anchor, body, resources) in enumerate(RESOURCE_GROUPS):
            group, _ = ResourceGroup.objects.update_or_create(
                heading=heading, defaults={"body": body, "order": index})
            for link_index, (title, url, note) in enumerate(resources):
                Resource.objects.update_or_create(
                    group=group, title=title,
                    defaults={"url": url, "note": note, "order": link_index})
                links += 1
        counts["resource groups"] = len(RESOURCE_GROUPS)
        counts["resources"] = links

        from .seed_activities import ACTIVITIES

        for index, spec in enumerate(ACTIVITIES):
            activity, _ = Activity.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "name": spec["name"],
                    "cadence": spec["cadence"],
                    "cadence_is_primary": spec.get("primary", False),
                    "extra_tag": spec.get("extra_tag", ""),
                    "summary": spec["summary"],
                    "body": spec.get("body", ""),
                    "index_bullets": spec.get("index_bullets", ""),
                    "order": index,
                },
            )
            activity.sections.all().delete()
            for section_index, section in enumerate(spec.get("sections", [])):
                ActivitySection.objects.create(
                    activity=activity,
                    heading=section["heading"],
                    body=section.get("body", ""),
                    bullets=section.get("bullets", ""),
                    bullets_in_columns=section.get("columns", False),
                    note_title=section.get("note_title", ""),
                    order=section_index,
                )
        counts["activities"] = len(ACTIVITIES)

        from .seed_pages import PAGES, load_pages

        load_pages()
        counts["pages"] = len(PAGES)

        if loud:
            for label, count in counts.items():
                self.stdout.write(f"  {count:>3}  {label}")
        self.stdout.write(self.style.SUCCESS("Content loaded."))
