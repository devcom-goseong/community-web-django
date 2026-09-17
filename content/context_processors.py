"""What every page needs: the site settings, the platform links, and who is looking.

This is where the rule that invite links are for members is enforced. A link
marked members-only is turned into a name and a badge before any template sees
it, so its address is never in the HTML sent to someone who is not a member —
not hidden with CSS, not in a comment, not anywhere a "view source" would find.

Everything is lazy. The admin renders its pages through the same processors
and never uses any of this, so it should not pay for the queries.
"""

from dataclasses import dataclass

from django.utils.functional import SimpleLazyObject

from accounts.access import access_state, can_see_members_area, member_of

from .models import SiteSettings, SocialLink


@dataclass(frozen=True)
class LinkView:
    name: str
    url: str        # empty whenever the viewer may not have it
    handle: str
    state: str      # "live", "soon" (no address yet) or "members" (withheld)

    @property
    def is_live(self):
        return self.state == "live"


def link_views(group, user):
    allowed = can_see_members_area(user)
    views = []
    for link in SocialLink.objects.live().filter(group=group):
        if not link.url:
            views.append(LinkView(link.name, "", link.handle if not link.members_only else "",
                                  "soon"))
        elif link.members_only and not allowed:
            # The handle of a members-only platform can itself be an invite
            # code or a server name, so it is withheld along with the address.
            views.append(LinkView(link.name, "", "", "members"))
        else:
            views.append(LinkView(link.name, link.url, link.handle, "live"))
    return views


def site(request):
    user = getattr(request, "user", None)
    return {
        "site": SimpleLazyObject(SiteSettings.get),
        "chat_links": SimpleLazyObject(lambda: link_views(SocialLink.GROUP_CHAT, user)),
        "social_links": SimpleLazyObject(lambda: link_views(SocialLink.GROUP_SOCIAL, user)),
        "viewer_member": SimpleLazyObject(lambda: member_of(user)),
        "viewer_can_see_members": SimpleLazyObject(lambda: can_see_members_area(user)),
        "viewer_state": SimpleLazyObject(lambda: access_state(user)),
    }
