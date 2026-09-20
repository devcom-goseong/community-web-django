"""The Vault — a royal-styled admin console behind one password.

It is not a second copy of the Django admin. It *reflects* the admin: it
manages exactly the models registered on the default admin site, and it edits
exactly the fields that model's admin leaves editable (so a field the admin
marks read-only — like a member's status, which must change through the proper
channel so the emails go out — is read-only here too). The auth user and group
models are left to the Django admin at /royal-jelly/, where passwords and
permissions are handled properly.

Access is a single password kept in the environment (VAULT_PASSWORD). There is
no per-user login and no accountability trail, so it is a blunt, powerful tool:
the gate is the whole of the security, which is why the password is long and
lives only in the server environment, never in the code.
"""

import functools

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import Group, User
from django.core.paginator import Paginator
from django.db.models import Q
from django.forms import modelform_factory
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

SESSION_KEY = "vault_ok"
NEXT_KEY = "vault_next"
# Kept in the Django admin, not here: creating or editing these safely means
# hashing passwords and handling permissions, which the stock admin already does.
EXCLUDED = {User, Group}


def managed():
    """Ordered {label: (model, model_admin)} for what the admin manages."""
    out = {}
    for model, model_admin in admin.site._registry.items():
        if model in EXCLUDED:
            continue
        label = f"{model._meta.app_label}.{model._meta.model_name}"
        out[label] = (model, model_admin)
    return dict(sorted(out.items()))


def _lookup(label):
    found = managed().get(label)
    if not found:
        raise Http404("No such section")
    return found


def vault_required(view):
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.session.get(SESSION_KEY):
            request.session[NEXT_KEY] = request.get_full_path()
            return redirect("vault:unlock")
        return view(request, *args, **kwargs)

    return wrapped


def unlock(request):
    if request.session.get(SESSION_KEY):
        return redirect("vault:dashboard")
    error = ""
    if request.method == "POST":
        if settings.VAULT_PASSWORD and request.POST.get("password", "") == settings.VAULT_PASSWORD:
            request.session[SESSION_KEY] = True
            request.session.set_expiry(60 * 60 * 12)  # 12 hours
            return redirect(request.session.pop(NEXT_KEY, None) or "vault:dashboard")
        error = "That is not the vault password."
    return render(request, "vault/unlock.html", {"error": error})


def lock(request):
    request.session.pop(SESSION_KEY, None)
    return redirect("vault:unlock")


@vault_required
def dashboard(request):
    groups = {}
    for label, (model, _ma) in managed().items():
        app = model._meta.app_config.verbose_name
        groups.setdefault(app, []).append({
            "label": label,
            "name": model._meta.verbose_name_plural.title(),
            "count": model._default_manager.count(),
        })
    return render(request, "vault/dashboard.html", {"groups": groups})


def _columns(model, model_admin):
    cols = [c for c in getattr(model_admin, "list_display", []) if isinstance(c, str)]
    return cols or ["__str__"]


def _cell(obj, model_admin, column):
    if column == "__str__":
        return str(obj)
    value = getattr(obj, column, None)
    if callable(value):
        try:
            value = value()
        except Exception:
            value = ""
    if value in (None, "") and hasattr(model_admin, column):
        try:
            value = getattr(model_admin, column)(obj)
        except Exception:
            value = ""
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "" if value is None else str(value)


@vault_required
def object_list(request, label):
    model, model_admin = _lookup(label)
    qs = model._default_manager.all()
    query = request.GET.get("q", "").strip()
    search_fields = [f.lstrip("^=@") for f in getattr(model_admin, "search_fields", []) or []]
    if query and search_fields:
        cond = Q()
        for field in search_fields:
            cond |= Q(**{f"{field}__icontains": query})
        qs = qs.filter(cond)
    columns = _columns(model, model_admin)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    rows = [{"pk": obj.pk, "cells": [_cell(obj, model_admin, c) for c in columns]} for obj in page]
    heads = [("Name" if c == "__str__" else c.replace("_", " ").title()) for c in columns]
    return render(request, "vault/list.html", {
        "label": label,
        "title": model._meta.verbose_name_plural.title(),
        "singular": model._meta.verbose_name.title(),
        "heads": heads,
        "rows": rows,
        "page": page,
        "q": query,
        "has_search": bool(search_fields),
    })


def _form_class(model, model_admin):
    readonly = set(getattr(model_admin, "readonly_fields", []) or [])
    fields = [f.name for f in model._meta.fields
              if f.editable and not f.auto_created and f.name not in readonly]
    fields += [f.name for f in model._meta.many_to_many if f.name not in readonly]
    return modelform_factory(model, fields=fields)


@vault_required
def object_edit(request, label, pk=None):
    model, model_admin = _lookup(label)
    form_class = _form_class(model, model_admin)
    instance = get_object_or_404(model, pk=pk) if pk is not None else None
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            obj = form.save()
            verb = "Updated" if instance else "Created"
            messages.success(request, f"{verb} {model._meta.verbose_name} “{obj}”.")
            return redirect("vault:list", label=label)
    else:
        form = form_class(instance=instance)
    return render(request, "vault/form.html", {
        "label": label,
        "form": form,
        "instance": instance,
        "title": model._meta.verbose_name.title(),
    })


@vault_required
def object_delete(request, label, pk):
    model, _ma = _lookup(label)
    obj = get_object_or_404(model, pk=pk)
    if request.method == "POST":
        shown = str(obj)
        obj.delete()
        messages.success(request, f"Deleted {model._meta.verbose_name} “{shown}”.")
        return redirect("vault:list", label=label)
    return render(request, "vault/delete.html", {
        "label": label,
        "object": obj,
        "title": model._meta.verbose_name.title(),
    })
