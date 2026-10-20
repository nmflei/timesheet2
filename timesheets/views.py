from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import (
    ClientForm,
    DayEntryFormSet,
    EmployeeForm,
    ProjectForm,
    ReviewForm,
    TimesheetCreateForm,
)
from .models import Client, DayEntry, EmployeeProfile, Project, Timesheet, TimesheetHistory


def is_manager(user):
    return user.is_staff or user.is_superuser


def can_review(user, timesheet):
    return is_manager(user) or (
        user.is_authenticated
        and user.email
        and user.email.casefold() == timesheet.project.approver_email.casefold()
    )


@require_POST
def set_language(request):
    language = request.POST.get("language")
    available_languages = dict(settings.LANGUAGES)
    if language not in available_languages:
        messages.error(request, _("Selecione um idioma válido."))
        return redirect("dashboard" if request.user.is_authenticated else "login")

    translation.activate(language)
    request.LANGUAGE_CODE = language
    response = HttpResponseRedirect(
        request.POST.get("next")
        if url_has_allowed_host_and_scheme(
            request.POST.get("next", ""),
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
        else "/"
    )
    response.set_cookie(
        settings.SESSION_LANGUAGE_COOKIE_NAME,
        language,
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )
    response.delete_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
    )
    return response


@login_required
def dashboard(request):
    sheets = Timesheet.objects.select_related("client", "project", "employee").prefetch_related(
        "entries"
    )
    if not is_manager(request.user):
        sheets = sheets.filter(employee=request.user)
    return render(request, "timesheets/dashboard.html", {"timesheets": sheets})


@login_required
def projects_for_client(request, client_id):
    projects = Project.objects.filter(client_id=client_id).order_by("name")
    return JsonResponse([{"id": project.id, "name": project.name} for project in projects], safe=False)


@login_required
def timesheet_create(request):
    if request.method == "POST":
        form = TimesheetCreateForm(request.POST)
        if form.is_valid():
            sheet = form.save(commit=False)
            sheet.employee = request.user
            try:
                with transaction.atomic():
                    sheet.full_clean(validate_constraints=False)
                    sheet.save()
                    for day in range(7):
                        DayEntry.objects.create(
                            timesheet=sheet, entry_date=sheet.week_start + timedelta(days=day)
                        )
                    TimesheetHistory.objects.create(
                        timesheet=sheet, actor=request.user, status=sheet.status
                    )
            except IntegrityError:
                form.add_error(None, _("Já existe uma folha para este projeto e semana."))
            else:
                return redirect("timesheet_detail", pk=sheet.pk)
    else:
        form = TimesheetCreateForm()
    return render(request, "timesheets/timesheet_create.html", {"form": form})


@login_required
def timesheet_detail(request, pk):
    sheet = get_object_or_404(
        Timesheet.objects.select_related("client", "project", "employee"), pk=pk
    )
    if sheet.employee_id != request.user.id and not is_manager(request.user) and not can_review(request.user, sheet):
        raise PermissionDenied

    editable = sheet.employee_id == request.user.id and sheet.status in {
        Timesheet.Status.DRAFT,
        Timesheet.Status.RETURNED,
    }
    formset = DayEntryFormSet(
        request.POST or None,
        queryset=sheet.entries.all(),
        prefix="days",
    )
    if request.method == "POST":
        if not editable:
            raise PermissionDenied
        if formset.is_valid():
            with transaction.atomic():
                formset.save()
            messages.success(request, _("Folha de horas guardada."))
            return redirect("timesheet_detail", pk=sheet.pk)
        messages.error(request, _("Verifique os dados dos registos diários."))
    review_form = ReviewForm()
    return render(
        request,
        "timesheets/timesheet_detail.html",
        {
            "timesheet": sheet,
            "formset": formset,
            "editable": editable,
            "review_form": review_form,
            "can_review": can_review(request.user, sheet),
            "history": sheet.history.select_related("actor"),
        },
    )


@login_required
@require_POST
def timesheet_submit(request, pk):
    sheet = get_object_or_404(Timesheet, pk=pk, employee=request.user)
    if sheet.status not in {Timesheet.Status.DRAFT, Timesheet.Status.RETURNED}:
        raise PermissionDenied
    if not sheet.entries.filter(start_time__isnull=False, end_time__isnull=False).exists():
        messages.error(request, _("Registe pelo menos um dia antes de submeter a folha."))
        return redirect("timesheet_detail", pk=pk)
    with transaction.atomic():
        sheet.status = Timesheet.Status.SUBMITTED
        sheet.save(update_fields=["status", "updated_at"])
        TimesheetHistory.objects.create(
            timesheet=sheet, actor=request.user, status=sheet.status
        )
    messages.success(request, _("Folha submetida para aprovação."))
    return redirect("timesheet_detail", pk=pk)


@login_required
def approval_list(request):
    sheets = Timesheet.objects.filter(status=Timesheet.Status.SUBMITTED).select_related(
        "employee", "client", "project"
    ).prefetch_related("entries")
    if not is_manager(request.user):
        sheets = sheets.filter(project__approver_email__iexact=request.user.email)
    return render(request, "timesheets/approval_list.html", {"timesheets": sheets})


@login_required
@require_POST
def timesheet_review(request, pk):
    sheet = get_object_or_404(Timesheet, pk=pk)
    if not can_review(request.user, sheet):
        raise PermissionDenied
    if sheet.status != Timesheet.Status.SUBMITTED:
        messages.error(request, _("Esta folha já não aguarda aprovação."))
        return redirect("timesheet_detail", pk=pk)
    form = ReviewForm(request.POST)
    if not form.is_valid():
        messages.error(request, _("Para devolver uma folha, indique o motivo."))
        return redirect("timesheet_detail", pk=pk)
    status = (
        Timesheet.Status.APPROVED
        if form.cleaned_data["action"] == "approve"
        else Timesheet.Status.RETURNED
    )
    with transaction.atomic():
        sheet.status = status
        sheet.save(update_fields=["status", "updated_at"])
        TimesheetHistory.objects.create(
            timesheet=sheet,
            actor=request.user,
            status=status,
            note=form.cleaned_data["note"].strip(),
        )
    messages.success(request, _("Decisão registada."))
    return redirect("timesheet_detail", pk=pk)


@login_required
def client_list(request):
    if not is_manager(request.user):
        raise PermissionDenied
    return render(
        request,
        "timesheets/client_list.html",
        {
            "clients": Client.objects.prefetch_related("projects"),
            "title": _("Clientes"),
        },
    )


@login_required
def client_detail(request, pk):
    if not is_manager(request.user):
        raise PermissionDenied
    client = get_object_or_404(Client.objects.prefetch_related("projects"), pk=pk)
    return render(request, "timesheets/client_detail.html", {"client": client})


@login_required
def client_create(request):
    return manage_object(request, ClientForm, "timesheets/object_form.html", _("Novo cliente"), "client_list")


@login_required
def client_edit(request, pk):
    return manage_object(request, ClientForm, "timesheets/object_form.html", _("Editar cliente"), "client_list", Client, pk)


@login_required
def project_list(request):
    if not is_manager(request.user):
        raise PermissionDenied
    return render(request, "timesheets/management_list.html", {
        "title": _("Projetos"),
        "objects": Project.objects.select_related("client"),
        "create_url": "project_create",
        "edit_url": "project_edit",
        "object_label": _("projeto"),
    })


@login_required
def project_create(request):
    return manage_object(request, ProjectForm, "timesheets/object_form.html", _("Novo projeto"), "project_list")


@login_required
def project_create_for_client(request, pk):
    if not is_manager(request.user):
        raise PermissionDenied
    client = get_object_or_404(Client, pk=pk)
    return manage_object(
        request,
        ProjectForm,
        "timesheets/object_form.html",
        _("Novo projeto"),
        "client_detail",
        success_kwargs={"pk": client.pk},
        form_kwargs={"fixed_client": client},
    )


@login_required
def project_edit(request, pk):
    return manage_object(request, ProjectForm, "timesheets/object_form.html", _("Editar projeto"), "project_list", Project, pk)


@login_required
def employee_list(request):
    if not is_manager(request.user):
        raise PermissionDenied
    employees = EmployeeProfile.objects.select_related("user").all()
    return render(request, "timesheets/employee_list.html", {"employees": employees})


@login_required
def employee_create(request):
    if not is_manager(request.user):
        raise PermissionDenied
    form = EmployeeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not settings.DEBUG and not settings.EMAIL_HOST:
            form.add_error(
                None,
                _("Configure o SMTP antes de criar colaboradores para poder enviar o convite seguro."),
            )
        else:
            with transaction.atomic():
                user = form.save()
                reset_form = PasswordResetForm({"email": user.email})
                if not reset_form.is_valid():
                    raise RuntimeError("Could not prepare the employee password setup email.")
                reset_form.save(
                    request=request,
                    use_https=request.is_secure(),
                    email_template_name="registration/password_reset_email.txt",
                    subject_template_name="registration/password_reset_subject.txt",
                )
            messages.success(request, _("Colaborador criado e ligação segura para definir a palavra-passe enviada por email."))
            return redirect("employee_list")
    return render(request, "timesheets/employee_form.html", {"form": form, "title": _("Novo colaborador")})


@login_required
def employee_edit(request, pk):
    if not is_manager(request.user):
        raise PermissionDenied
    profile = get_object_or_404(EmployeeProfile.objects.select_related("user"), pk=pk)
    form = EmployeeForm(request.POST or None, instance=profile.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Dados do colaborador atualizados."))
        return redirect("employee_list")
    return render(request, "timesheets/employee_form.html", {"form": form, "title": _("Editar colaborador")})


@login_required
@require_POST
def employee_toggle_active(request, pk):
    if not is_manager(request.user):
        raise PermissionDenied
    profile = get_object_or_404(EmployeeProfile.objects.select_related("user"), pk=pk)
    profile.user.is_active = not profile.user.is_active
    profile.user.save(update_fields=["is_active"])
    messages.success(
        request,
        _("Conta do colaborador ativada.") if profile.user.is_active else _("Conta do colaborador desativada."),
    )
    return redirect("employee_list")


def manage_object(
    request,
    form_class,
    template,
    title,
    success_url,
    model=None,
    pk=None,
    form_kwargs=None,
    success_kwargs=None,
):
    if not is_manager(request.user):
        raise PermissionDenied
    instance = get_object_or_404(model, pk=pk) if model and pk else None
    form = form_class(request.POST or None, instance=instance, **(form_kwargs or {}))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("%(title)s guardado.") % {"title": title})
        return redirect(success_url, **(success_kwargs or {}))
    return render(request, template, {"form": form, "title": title})
