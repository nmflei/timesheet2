from datetime import timedelta
from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


CENT = Decimal("0.01")


class Client(models.Model):
    company_name = models.CharField(_("nome da empresa"), max_length=180)
    address = models.TextField(_("morada completa"))
    tax_number = models.CharField(_("NIF"), max_length=20, unique=True)
    contact_name = models.CharField(_("nome do contacto"), max_length=160)
    email = models.EmailField(_("email"))
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        ordering = ["company_name"]
        verbose_name = _("cliente")
        verbose_name_plural = _("clientes")

    def __str__(self):
        return self.company_name


class Project(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.PROTECT, related_name="projects", verbose_name=_("cliente")
    )
    name = models.CharField(_("nome do projeto"), max_length=180)
    location = models.CharField(_("localização"), max_length=240)
    approver_name = models.CharField(_("responsável pela aprovação"), max_length=160)
    approver_email = models.EmailField(_("email do responsável"))
    normal_hour_rate = models.DecimalField(
        _("preço por hora normal (€)"),
        max_digits=9,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    overtime_hour_rate = models.DecimalField(
        _("preço por hora extra (€)"),
        max_digits=9,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    sunday_hour_rate = models.DecimalField(
        _("preço por hora ao domingo (€)"),
        max_digits=9,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        ordering = ["client__company_name", "name"]
        verbose_name = _("projeto")
        verbose_name_plural = _("projetos")
        constraints = [
            models.UniqueConstraint(fields=["client", "name"], name="unique_project_name_per_client")
        ]

    def __str__(self):
        return f"{self.client} — {self.name}"


class Timesheet(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Rascunho")
        SUBMITTED = "submitted", _("Submetida")
        APPROVED = "approved", _("Aprovada")
        RETURNED = "returned", _("Devolvida")

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="timesheets",
        verbose_name=_("colaborador"),
    )
    week_start = models.DateField(_("segunda-feira da semana"))
    client = models.ForeignKey(Client, on_delete=models.PROTECT, verbose_name=_("cliente"))
    project = models.ForeignKey(Project, on_delete=models.PROTECT, verbose_name=_("projeto"))
    status = models.CharField(
        _("estado"), max_length=12, choices=Status.choices, default=Status.DRAFT
    )
    created_at = models.DateTimeField(_("criada em"), auto_now_add=True)
    updated_at = models.DateTimeField(_("atualizada em"), auto_now=True)

    class Meta:
        ordering = ["-week_start", "-created_at"]
        verbose_name = _("folha de horas")
        verbose_name_plural = _("folhas de horas")
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "week_start", "client", "project"],
                name="unique_employee_week_client_project",
            )
        ]

    def __str__(self):
        return f"{self.employee} — semana de {self.week_start:%d/%m/%Y} — {self.project.name}"

    def clean(self):
        errors = {}
        if self.week_start and self.week_start.weekday() != 0:
            errors["week_start"] = _("A semana tem de começar à segunda-feira.")
        if self.project_id and self.client_id and self.project.client_id != self.client_id:
            errors["project"] = _("O projeto selecionado não pertence ao cliente escolhido.")
        if errors:
            raise ValidationError(errors)

    @property
    def normal_hours(self):
        return sum((entry.normal_hours for entry in self.entries.all()), Decimal("0"))

    @property
    def overtime_hours(self):
        return sum((entry.overtime_hours for entry in self.entries.all()), Decimal("0"))

    @property
    def sunday_hours(self):
        return sum((entry.sunday_hours for entry in self.entries.all()), Decimal("0"))

    @property
    def total_hours(self):
        return self.normal_hours + self.overtime_hours + self.sunday_hours

    @property
    def normal_amount(self):
        return sum((entry.normal_amount for entry in self.entries.all()), Decimal("0"))

    @property
    def overtime_amount(self):
        return sum((entry.overtime_amount for entry in self.entries.all()), Decimal("0"))

    @property
    def sunday_amount(self):
        return sum((entry.sunday_amount for entry in self.entries.all()), Decimal("0"))

    @property
    def total_amount(self):
        return self.normal_amount + self.overtime_amount + self.sunday_amount


class DayEntry(models.Model):
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.CASCADE, related_name="entries", verbose_name=_("folha")
    )
    entry_date = models.DateField(_("dia"))
    start_time = models.TimeField(_("início"), null=True, blank=True)
    end_time = models.TimeField(_("fim"), null=True, blank=True)
    break_minutes = models.PositiveSmallIntegerField(_("pausa (minutos)"), default=0)

    class Meta:
        ordering = ["entry_date"]
        verbose_name = _("registo diário")
        verbose_name_plural = _("registos diários")
        constraints = [
            models.UniqueConstraint(fields=["timesheet", "entry_date"], name="unique_entry_per_day")
        ]

    def __str__(self):
        return f"{self.entry_date:%A %d/%m} — {self.timesheet}"

    def clean(self):
        if not self.timesheet_id or not self.entry_date:
            return
        monday = self.timesheet.week_start
        if not monday <= self.entry_date <= monday + timedelta(days=6):
            raise ValidationError({"entry_date": _("O dia tem de pertencer à semana da folha.")})
        if (self.start_time is None) != (self.end_time is None):
            raise ValidationError(_("Indique a hora de início e de fim."))
        if self.start_time is None and self.break_minutes:
            raise ValidationError({"break_minutes": _("Registe primeiro o início e o fim do dia.")})
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": _("A hora de fim tem de ser posterior ao início.")})
        if self.start_time and self.end_time and self.break_minutes > self.elapsed_minutes:
            raise ValidationError({"break_minutes": _("A pausa não pode exceder o intervalo registado.")})

    @property
    def elapsed_minutes(self):
        if not self.start_time or not self.end_time:
            return 0
        start = self.start_time.hour * 60 + self.start_time.minute
        end = self.end_time.hour * 60 + self.end_time.minute
        return end - start

    @property
    def total_hours(self):
        return Decimal(self.elapsed_minutes) / Decimal(60)

    @property
    def normal_hours(self):
        if self.entry_date.weekday() >= 5:
            return Decimal("0")
        return min(self.total_hours, Decimal("8"))

    @property
    def overtime_hours(self):
        if self.entry_date.weekday() == 5:
            return self.total_hours
        if self.entry_date.weekday() == 6:
            return Decimal("0")
        return max(self.total_hours - Decimal("8"), Decimal("0"))

    @property
    def sunday_hours(self):
        if self.entry_date.weekday() == 6:
            return self.total_hours
        return Decimal("0")

    def _amount_for(self, hours, rate):
        return (hours * rate).quantize(CENT, rounding=ROUND_HALF_UP)

    @property
    def normal_amount(self):
        return self._amount_for(self.normal_hours, self.timesheet.project.normal_hour_rate)

    @property
    def overtime_amount(self):
        return self._amount_for(self.overtime_hours, self.timesheet.project.overtime_hour_rate)

    @property
    def sunday_amount(self):
        return self._amount_for(self.sunday_hours, self.timesheet.project.sunday_hour_rate)

    @property
    def total_amount(self):
        return self.normal_amount + self.overtime_amount + self.sunday_amount


class TimesheetHistory(models.Model):
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.CASCADE, related_name="history", verbose_name=_("folha")
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, verbose_name=_("utilizador")
    )
    status = models.CharField(_("estado"), max_length=12, choices=Timesheet.Status.choices)
    note = models.TextField(_("nota"), blank=True)
    created_at = models.DateTimeField(_("data"), auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("registo de estado")
        verbose_name_plural = _("histórico de estados")


class UserLanguagePreference(models.Model):
    class Language(models.TextChoices):
        PORTUGUESE = "pt-pt", _("Português (Portugal)")
        ENGLISH = "en", _("English")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="language_preference",
        verbose_name=_("utilizador"),
    )
    language = models.CharField(
        _("idioma"),
        max_length=5,
        choices=Language.choices,
        default=Language.PORTUGUESE,
    )

    class Meta:
        verbose_name = _("preferência de idioma")
        verbose_name_plural = _("preferências de idioma")

    def __str__(self):
        return f"{self.user} — {self.get_language_display()}"

    def __str__(self):
        return f"{self.get_status_display()} — {self.created_at:%d/%m/%Y %H:%M}"
