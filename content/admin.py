"""The editing screens.

Grouped and labelled for people who will not be reading the code. Every list
shows whether a thing is published and lets it be reordered, and the bulk
publish/unpublish actions are on everything so a page can be pulled without a
deploy.
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    Activity,
    ActivitySection,
    Fact,
    FaqEntry,
    HomeCard,
    InterestArea,
    JoinStep,
    Page,
    PageSection,
    Resource,
    ResourceGroup,
    ResponsibilityArea,
    SiteSettings,
    SocialLink,
    Value,
)


class PublishActionsMixin:
    actions = ("publish", "unpublish")

    @admin.action(description="Publish")
    def publish(self, request, queryset):
        count = queryset.update(published=True)
        self.message_user(request, f"{count} published.", messages.SUCCESS)

    @admin.action(description="Hide from the site")
    def unpublish(self, request, queryset):
        count = queryset.update(published=False)
        self.message_user(request, f"{count} hidden.", messages.WARNING)

    @admin.display(description="live", boolean=True, ordering="published")
    def is_live(self, obj):
        return obj.published


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("The community", {"fields": ("community_name", "university", "country", "founded")}),
        ("Footer", {"fields": ("footer_blurb",)}),
    )

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class PageSectionInline(admin.StackedInline):
    model = PageSection
    extra = 1
    fields = ("order", "heading", "anchor", "body", "bullets")
    prepopulated_fields = {"anchor": ("heading",)}


@admin.register(Page)
class PageAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "slug", "layout", "section_count", "is_live", "order", "updated_at")
    list_editable = ("order",)
    list_filter = ("published", "layout")
    search_fields = ("title", "lead", "sections__heading", "sections__body")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PageSectionInline]
    fieldsets = (
        ("Heading", {"fields": ("title", "slug", "eyebrow", "lead")}),
        ("Opening", {"fields": ("notice_title", "notice_body", "intro")}),
        ("Version", {"fields": ("show_version", "version", "reviewed_on"),
                     "description": "For the rules, terms and privacy notice."}),
        ("Display", {"fields": ("layout", "published", "order")}),
    )

    @admin.display(description="sections")
    def section_count(self, obj):
        return obj.sections.count()


class ActivitySectionInline(admin.StackedInline):
    model = ActivitySection
    extra = 1
    fields = ("order", "heading", "body", "bullets", "bullets_in_columns", "note_title")


@admin.register(Activity)
class ActivityAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("name", "cadence", "extra_tag", "section_count", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published", "cadence_is_primary")
    search_fields = ("name", "summary", "body", "sections__heading", "sections__body")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ActivitySectionInline]
    fieldsets = (
        ("Identity", {"fields": ("name", "slug")}),
        ("How often", {"fields": ("cadence", "cadence_is_primary", "extra_tag")}),
        ("On the activities page", {"fields": ("summary", "body", "index_bullets")}),
        ("Display", {"fields": ("published", "order")}),
    )

    @admin.display(description="sections")
    def section_count(self, obj):
        return obj.sections.count()


@admin.register(HomeCard)
class HomeCardAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "icon", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published",)


@admin.register(Fact)
class FactAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("label", "value", "is_live", "order")
    list_editable = ("value", "order")
    list_filter = ("published",)


@admin.register(SocialLink)
class SocialLinkAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("name", "group", "url", "handle", "is_live", "order")
    list_editable = ("url", "handle", "order")
    list_filter = ("group", "published")
    search_fields = ("name", "handle")
    fieldsets = (
        (None, {
            "fields": ("name", "group", "url", "handle"),
            "description": "Leave the address blank and the site lists the platform with a "
                           "'Soon' badge instead of a link, which is better than a link that "
                           "goes nowhere. Fill it in and it becomes a real link on every page "
                           "at once.",
        }),
        ("Visibility", {"fields": ("published", "order")}),
    )


@admin.register(Value)
class ValueAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published",)
    search_fields = ("title", "body")


@admin.register(ResponsibilityArea)
class ResponsibilityAreaAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("name", "subtitle", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published",)
    search_fields = ("name", "bullets")


@admin.register(JoinStep)
class JoinStepAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published",)


@admin.register(FaqEntry)
class FaqEntryAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("question", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published",)
    search_fields = ("question", "answer")
    prepopulated_fields = {"anchor": ("question",)}


@admin.register(InterestArea)
class InterestAreaAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("name", "subtitle", "on_form", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published", "on_application_form")
    search_fields = ("name", "bullets")

    @admin.display(description="on the form", boolean=True, ordering="on_application_form")
    def on_form(self, obj):
        return obj.on_application_form


class ResourceInline(admin.TabularInline):
    model = Resource
    extra = 1
    fields = ("order", "title", "url", "note", "published")


@admin.register(ResourceGroup)
class ResourceGroupAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("heading", "link_count", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published",)
    prepopulated_fields = {"anchor": ("heading",)}
    inlines = [ResourceInline]

    @admin.display(description="links")
    def link_count(self, obj):
        return obj.links.count()


@admin.register(Resource)
class ResourceAdmin(PublishActionsMixin, admin.ModelAdmin):
    list_display = ("title", "group", "link", "is_live", "order")
    list_editable = ("order",)
    list_filter = ("published", "group")
    search_fields = ("title", "url", "note")

    @admin.display(description="url")
    def link(self, obj):
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', obj.url, obj.url[:48])
