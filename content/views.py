from django.conf import settings
from django.shortcuts import get_object_or_404, render

from .models import (
    Activity,
    Fact,
    FaqEntry,
    HomeCard,
    InterestArea,
    JoinStep,
    Page,
    ResourceGroup,
    ResponsibilityArea,
    SiteSettings,
    Value,
)


def base_context(request, title, description, nav=""):
    return {
        "site": SiteSettings.get(),
        "page_title": title,
        "page_description": description,
        "nav": nav,
    }


def home(request):
    context = base_context(
        request,
        "Building things together at Kyungdong University",
        "A developer community based at Kyungdong University, South Korea, open to students "
        "there and to any other developer. Weekly meetings, study groups, projects, hackathons "
        "and demo days, at every skill level.",
        nav="home",
    )
    context.update({
        "facts": Fact.objects.live(),
        "cards": HomeCard.objects.live(),
        "activities": Activity.objects.live(),
        "interests": InterestArea.objects.live(),
    })
    return render(request, "pages/home.html", context)


def about(request):
    context = base_context(
        request,
        "About",
        "How the community started, what it is for, the values it holds members to, how the "
        "work is divided, and how to become a member.",
        nav="about",
    )
    context.update({
        "values": Value.objects.live(),
        "areas": ResponsibilityArea.objects.live(),
        "steps": JoinStep.objects.live(),
        "rules_page": Page.objects.filter(slug="rules", published=True).first(),
    })
    return render(request, "pages/about.html", context)


def activities(request):
    context = base_context(
        request,
        "Activities",
        "Weekly community meetings, member-run study groups, idea submissions, project teams, "
        "hackathons, demo days and monthly in-person meetups.",
        nav="activities",
    )
    context["activities"] = Activity.objects.live().prefetch_related("sections")
    return render(request, "pages/activities.html", context)


def activity(request, slug):
    item = get_object_or_404(Activity.objects.live().prefetch_related("sections"), slug=slug)
    context = base_context(request, item.name, item.summary, nav="activities")
    context.update({
        "activity": item,
        "others": Activity.objects.live().exclude(pk=item.pk),
    })
    return render(request, "pages/activity.html", context)


def page(request, slug):
    item = get_object_or_404(Page.objects.live().prefetch_related("sections"), slug=slug)
    context = base_context(request, item.title, item.lead, nav=slug)
    context["page"] = item
    return render(request, "pages/page.html", context)


def faq(request):
    context = base_context(
        request,
        "Questions",
        "Do you have to be a KDU student, do you need to code already, how much time it takes, "
        "and what happens after you apply.",
    )
    context["entries"] = FaqEntry.objects.live()
    return render(request, "pages/faq.html", context)


def interests(request):
    context = base_context(
        request,
        "What you can get into",
        "The areas the community works across, what each one involves here, and who it suits.",
    )
    context["interests"] = InterestArea.objects.live()
    return render(request, "pages/interests.html", context)


def resources(request):
    context = base_context(
        request,
        "Where to start",
        "A short list of genuinely good starting points, and how the community shares the rest.",
    )
    context["groups"] = ResourceGroup.objects.live().prefetch_related("links")
    return render(request, "pages/resources.html", context)


def contents(request):
    context = base_context(
        request,
        "Everything on this site",
        "Every page, grouped, so you can find the one you want without hunting through the "
        "navigation.",
    )
    context.update({
        "activities": Activity.objects.live(),
        "pages": Page.objects.live(),
    })
    return render(request, "pages/contents.html", context)


def join(request):
    context = base_context(
        request,
        "Join or contact us",
        "Apply to join the community, or send a question. One short form: who you are, what you "
        "are interested in, and what you would like to say.",
        nav="join",
    )
    context.update({
        "interests": InterestArea.objects.live().filter(on_application_form=True),
        "steps": JoinStep.objects.live(),
        "endpoint": settings.FORM_ENDPOINT,
    })
    return render(request, "pages/join.html", context)
