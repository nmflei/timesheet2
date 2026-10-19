from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import (
    Client,
    DayEntry,
    Project,
    Timesheet,
    TimesheetHistory,
    UserLanguagePreference,
)


class UserLanguagePreferenceInline(admin.StackedInline):
    model = UserLanguagePreference
    can_delete = False
    extra = 0
    verbose_name = _("preferência de idioma")


admin.site.unregister(get_user_model())


@admin.register(get_user_model())
class CustomUserAdmin(UserAdmin):
    inlines = [UserLanguagePreferenceInline]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("company_name", "tax_number", "contact_name", "email")
    search_fields = ("company_name", "tax_number", "contact_name", "email")


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "client",
        "normal_hour_rate",
        "overtime_hour_rate",
        "sunday_hour_rate",
        "approver_name",
        "approver_email",
    )
    list_filter = ("client",)
    search_fields = ("name", "client__company_name", "approver_email")


class DayEntryInline(admin.TabularInline):
    model = DayEntry
    extra = 0
    readonly_fields = ("entry_date", "start_time", "end_time", "break_minutes")


@admin.register(Timesheet)
class TimesheetAdmin(admin.ModelAdmin):
    list_display = ("employee", "week_start", "client", "project", "status")
    list_filter = ("status", "client", "week_start")
    search_fields = ("employee__username", "employee__email", "project__name")
    readonly_fields = ("employee", "week_start", "client", "project", "status", "created_at", "updated_at")
    inlines = [DayEntryInline]


@admin.register(TimesheetHistory)
class TimesheetHistoryAdmin(admin.ModelAdmin):
    list_display = ("timesheet", "actor", "status", "created_at")
    readonly_fields = ("timesheet", "actor", "status", "note", "created_at")


@admin.register(UserLanguagePreference)
class UserLanguagePreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "language")
    list_filter = ("language",)
    search_fields = ("user__username", "user__email")
