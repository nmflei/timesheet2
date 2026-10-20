from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from .forms import TimesheetCreateForm
from .models import Client, DayEntry, Project, Timesheet


class TimesheetRulesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="ana", password="safe-password", email="ana@example.pt"
        )
        self.client_record = Client.objects.create(
            company_name="Cliente Exemplo",
            address="Rua Exemplo, Lisboa",
            tax_number="501234567",
            contact_name="Contacto",
            email="cliente@example.pt",
        )
        self.project = Project.objects.create(
            client=self.client_record,
            name="Projeto A",
            location="Lisboa",
            approver_name="Rui",
            approver_email="rui@example.pt",
            normal_hour_rate=Decimal("15.25"),
            overtime_hour_rate=Decimal("22.50"),
            sunday_hour_rate=Decimal("30.00"),
        )
        self.sheet = Timesheet.objects.create(
            employee=self.user,
            week_start=date(2026, 10, 19),
            client=self.client_record,
            project=self.project,
        )

    def test_break_is_informational_and_weekday_overtime_starts_after_eight_hours(self):
        entry = DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 19),
            start_time=time(9),
            end_time=time(18),
            break_minutes=60,
        )
        self.assertEqual(entry.total_hours, Decimal("9"))
        self.assertEqual(entry.normal_hours, Decimal("8"))
        self.assertEqual(entry.overtime_hours, Decimal("1"))

    def test_saturday_is_overtime_and_sunday_uses_only_sunday_rate(self):
        entry = DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 24),
            start_time=time(9),
            end_time=time(13),
            break_minutes=30,
        )
        self.assertEqual(entry.normal_hours, Decimal("0"))
        self.assertEqual(entry.overtime_hours, Decimal("4"))
        self.assertEqual(entry.sunday_hours, Decimal("0"))
        self.assertEqual(entry.total_amount, Decimal("90.00"))

        sunday_entry = DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 25),
            start_time=time(9),
            end_time=time(13),
            break_minutes=30,
        )
        self.assertEqual(sunday_entry.normal_hours, Decimal("0"))
        self.assertEqual(sunday_entry.overtime_hours, Decimal("0"))
        self.assertEqual(sunday_entry.sunday_hours, Decimal("4"))
        self.assertEqual(sunday_entry.sunday_amount, Decimal("120.00"))
        self.assertEqual(sunday_entry.total_amount, Decimal("120.00"))

    def test_week_amount_is_summed_from_daily_category_amounts(self):
        DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 19),
            start_time=time(9),
            end_time=time(18),
            break_minutes=60,
        )
        DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 24),
            start_time=time(9),
            end_time=time(13),
        )
        DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 25),
            start_time=time(9),
            end_time=time(13),
        )
        self.assertEqual(self.sheet.normal_hours, Decimal("8"))
        self.assertEqual(self.sheet.overtime_hours, Decimal("5"))
        self.assertEqual(self.sheet.sunday_hours, Decimal("4"))
        self.assertEqual(self.sheet.total_hours, Decimal("17"))
        self.assertEqual(self.sheet.normal_amount, Decimal("122.00"))
        self.assertEqual(self.sheet.overtime_amount, Decimal("112.50"))
        self.assertEqual(self.sheet.sunday_amount, Decimal("120.00"))
        self.assertEqual(self.sheet.total_amount, Decimal("354.50"))

    def test_project_form_rejects_negative_rates(self):
        from .forms import ProjectForm

        form = ProjectForm(
            data={
                "client": self.client_record.pk,
                "name": "Projeto Inválido",
                "location": "Lisboa",
                "approver_name": "Rui",
                "approver_email": "rui@example.pt",
                "normal_hour_rate": "-1.00",
                "overtime_hour_rate": "20.00",
                "sunday_hour_rate": "30.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("normal_hour_rate", form.errors)

    def test_sheet_must_start_on_monday_and_project_must_belong_to_client(self):
        with self.assertRaises(ValidationError):
            Timesheet(
                employee=self.user,
                week_start=date(2026, 10, 20),
                client=self.client_record,
                project=self.project,
            ).full_clean()
        another_client = Client.objects.create(
            company_name="Outro Cliente",
            address="Porto",
            tax_number="509876543",
            contact_name="Contacto",
            email="outro@example.pt",
        )
        with self.assertRaises(ValidationError):
            Timesheet(
                employee=self.user,
                week_start=date(2026, 10, 19),
                client=another_client,
                project=self.project,
            ).full_clean()

    def test_duplicate_sheet_is_blocked_by_database_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Timesheet.objects.create(
                    employee=self.user,
                    week_start=self.sheet.week_start,
                    client=self.client_record,
                    project=self.project,
                )

    def test_project_queryset_is_scoped_to_selected_client(self):
        other = Client.objects.create(
            company_name="Outro Cliente",
            address="Porto",
            tax_number="502222222",
            contact_name="Contacto",
            email="outro@example.pt",
        )
        other_project = Project.objects.create(
            client=other,
            name="Projeto B",
            location="Porto",
            approver_name="Rui",
            approver_email="rui@example.pt",
        )
        form = TimesheetCreateForm(
            data={
                "week_start": "2026-10-19",
                "client": self.client_record.pk,
                "project": other_project.pk,
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("project", form.errors)


class TimesheetWorkflowTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user(
            username="ana", password="safe-password", email="ana@example.pt"
        )
        self.approver = get_user_model().objects.create_user(
            username="rui", password="safe-password", email="rui@example.pt"
        )
        self.client_record = Client.objects.create(
            company_name="Cliente",
            address="Rua Exemplo",
            tax_number="501000001",
            contact_name="Contacto",
            email="cliente@example.pt",
        )
        self.project = Project.objects.create(
            client=self.client_record,
            name="Projeto",
            location="Lisboa",
            approver_name="Rui",
            approver_email="RUI@example.pt",
            normal_hour_rate=Decimal("15.00"),
            overtime_hour_rate=Decimal("25.00"),
            sunday_hour_rate=Decimal("30.00"),
        )
        self.sheet = Timesheet.objects.create(
            employee=self.employee,
            week_start=date(2026, 10, 19),
            client=self.client_record,
            project=self.project,
            status=Timesheet.Status.SUBMITTED,
        )
        DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 19),
            start_time=time(9),
            end_time=time(17),
        )

    def test_approver_email_can_view_and_return_sheet_with_note(self):
        self.client.force_login(self.approver)
        response = self.client.get(reverse("timesheet_detail", args=[self.sheet.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarifa hora normal")
        self.assertContains(response, "€/h")
        self.assertContains(response, "120,00 €")
        response = self.client.post(
            reverse("timesheet_review", args=[self.sheet.pk]),
            {"action": "return", "note": "Indique a tarefa realizada."},
        )
        self.assertRedirects(response, reverse("timesheet_detail", args=[self.sheet.pk]))
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.status, Timesheet.Status.RETURNED)
        self.assertEqual(self.sheet.history.latest("created_at").note, "Indique a tarefa realizada.")

    def test_timesheet_status_and_details_follow_approver_language(self):
        self.approver.language_preference.language = "en"
        self.approver.language_preference.save(update_fields=["language"])
        self.client.force_login(self.approver)
        response = self.client.get(reverse("timesheet_detail", args=[self.sheet.pk]))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Submitted")
        self.assertContains(response, "Regular hourly rate")
        self.assertContains(response, "Daily entries")
        self.assertContains(response, "Weekly total")

    def test_approver_cannot_return_sheet_without_note(self):
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("timesheet_review", args=[self.sheet.pk]),
            {"action": "return", "note": ""},
        )
        self.assertRedirects(response, reverse("timesheet_detail", args=[self.sheet.pk]))
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.status, Timesheet.Status.SUBMITTED)

    def test_employee_can_submit_a_recorded_sheet(self):
        sheet = Timesheet.objects.create(
            employee=self.employee,
            week_start=date(2026, 10, 26),
            client=self.client_record,
            project=self.project,
        )
        DayEntry.objects.create(
            timesheet=sheet,
            entry_date=date(2026, 10, 26),
            start_time=time(9),
            end_time=time(17),
        )
        self.client.force_login(self.employee)
        response = self.client.post(reverse("timesheet_submit", args=[sheet.pk]))
        self.assertRedirects(response, reverse("timesheet_detail", args=[sheet.pk]))
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, Timesheet.Status.SUBMITTED)
        self.assertEqual(sheet.history.latest("created_at").status, Timesheet.Status.SUBMITTED)

    def test_unrelated_user_cannot_review_sheet(self):
        stranger = get_user_model().objects.create_user(
            username="ines", password="safe-password", email="ines@example.pt"
        )
        self.client.force_login(stranger)
        response = self.client.post(
            reverse("timesheet_review", args=[self.sheet.pk]),
            {"action": "approve", "note": ""},
        )
        self.assertEqual(response.status_code, 403)

    def test_employee_can_only_see_own_sheets(self):
        stranger = get_user_model().objects.create_user(
            username="ines", password="safe-password", email="ines@example.pt"
        )
        self.client.force_login(stranger)
        response = self.client.get(reverse("timesheet_detail", args=[self.sheet.pk]))
        self.assertEqual(response.status_code, 403)


class LanguagePreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="language-user", password="safe-password", email="language@example.pt"
        )

    def test_new_user_defaults_to_portuguese(self):
        self.assertEqual(self.user.language_preference.language, "pt-pt")

    def test_authenticated_language_choice_is_saved_and_used_on_following_requests(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("dashboard")},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.user.language_preference.refresh_from_db()
        self.assertEqual(self.user.language_preference.language, "en")

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Weekly timesheets")
        self.assertContains(response, 'aria-label="Language"')
        self.assertContains(response, 'aria-label="Switch language to Portuguese (Portugal)"')
        self.assertContains(response, "portugal.svg")
        self.assertNotContains(response, "united-kingdom.svg")
        self.assertEqual(response.content.count(b'class="language-flag"'), 1)
        self.assertRegex(
            response.content.decode(),
            r'class="language-code">PT</span>\s*<img class="language-flag-icon" src="[^"]*portugal\.svg"',
        )
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'data-dark-label="Enable dark mode"')
        self.assertContains(response, "/static/timesheets/theme.js")
        self.assertContains(response, "/static/timesheets/style.css")
        self.assertNotContains(response, "<option")

    def test_language_preference_survives_a_new_session(self):
        self.user.language_preference.language = "en"
        self.user.language_preference.save(update_fields=["language"])
        another_session = self.client_class()
        another_session.force_login(self.user)
        response = another_session.get(reverse("login"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Log in")
        self.assertContains(response, "Use the account created by the administrator.")

    def test_anonymous_language_choice_is_kept_in_cookie(self):
        response = self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("login")},
        )
        self.assertRedirects(response, reverse("login"))
        response = self.client.get(reverse("login"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, "Log in")
        self.assertContains(response, 'aria-label="Language"')
        self.assertContains(response, 'aria-label="Switch language to Portuguese (Portugal)"')
        self.assertContains(response, "portugal.svg")
        self.assertNotContains(response, "united-kingdom.svg")
        self.assertEqual(response.content.count(b'class="language-flag"'), 1)
        self.assertRegex(
            response.content.decode(),
            r'class="language-code">PT</span>\s*<img class="language-flag-icon" src="[^"]*portugal\.svg"',
        )
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, "/static/timesheets/theme.js")
        self.assertContains(response, "/static/timesheets/style.css")

    def test_invalid_language_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post(reverse("set_language"), {"language": "fr", "next": "/"})
        self.user.language_preference.refresh_from_db()
        self.assertEqual(self.user.language_preference.language, "pt-pt")

    def test_admin_uses_saved_language_and_shows_language_selector(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-language", password="safe-password", email="admin@example.pt"
        )
        admin.language_preference.language = "en"
        admin.language_preference.save(update_fields=["language"])
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "en")
        self.assertContains(response, 'aria-label="Language"')
        self.assertContains(response, 'aria-label="Switch language to Portuguese (Portugal)"')
        self.assertContains(response, "portugal.svg")
        self.assertNotContains(response, "united-kingdom.svg")
        self.assertEqual(response.content.count(b'class="language-flag"'), 1)
        self.assertContains(response, "Site administration")
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'data-dark-label="Enable dark mode"')
        self.assertContains(response, "/static/timesheets/theme.js")

    def test_admin_login_is_localized_in_portuguese_and_has_language_selector(self):
        response = self.client.get(reverse("admin:login"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "pt-pt")
        self.assertContains(response, "Utilizador:")
        self.assertContains(response, "Palavra-passe:")
        self.assertContains(response, "Entrar")
        self.assertContains(response, 'aria-label="Idioma"')
        self.assertContains(response, 'aria-label="Mudar idioma para inglês"')
        self.assertContains(response, ">GB<")
        self.assertContains(response, "united-kingdom.svg")
        self.assertNotContains(response, "portugal.svg")
        self.assertEqual(response.content.count(b'class="language-flag"'), 1)
        self.assertRegex(
            response.content.decode(),
            r'class="language-code">GB</span>\s*<img class="language-flag-icon" src="[^"]*united-kingdom\.svg"',
        )
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, 'data-dark-label="Ativar modo escuro"')
        self.assertContains(response, 'class="site-theme-toggle"')
        self.assertContains(response, "/static/timesheets/theme.js")
        self.assertNotContains(response, "<option")
        admin = get_user_model().objects.create_superuser(
            username="admin-portugues", password="safe-password", email="admin-pt@example.pt"
        )
        self.client.force_login(admin)
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "Administração do site")
        self.assertContains(response, 'aria-label="Mudar idioma para inglês"')
        self.assertContains(response, ">GB<")
        self.assertContains(response, "united-kingdom.svg")
        self.assertNotContains(response, "portugal.svg")
        self.assertEqual(response.content.count(b'class="language-flag"'), 1)
        self.assertRegex(
            response.content.decode(),
            r'class="language-code">GB</span>\s*<img class="language-flag-icon" src="[^"]*united-kingdom\.svg"',
        )
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, "/static/timesheets/theme.js")

    def test_portuguese_dashboard_shows_only_the_english_switch(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "pt-pt")
        self.assertContains(response, 'aria-label="Mudar idioma para inglês"')
        self.assertContains(response, ">GB<")
        self.assertContains(response, "united-kingdom.svg")
        self.assertNotContains(response, "portugal.svg")
        self.assertEqual(response.content.count(b'class="language-flag"'), 1)
        self.assertRegex(
            response.content.decode(),
            r'class="language-code">GB</span>\s*<img class="language-flag-icon" src="[^"]*united-kingdom\.svg"',
        )
        self.assertContains(response, 'data-theme-toggle')
        self.assertContains(response, "/static/timesheets/theme.js")
        self.assertContains(response, "/static/timesheets/style.css")

    def test_model_validation_error_is_translated(self):
        client_record = Client.objects.create(
            company_name="Language client",
            address="Address",
            tax_number="509999999",
            contact_name="Contact",
            email="language-client@example.pt",
        )
        project = Project.objects.create(
            client=client_record,
            name="Language project",
            location="Location",
            approver_name="Approver",
            approver_email="approver@example.pt",
        )
        with translation.override("en"):
            with self.assertRaises(ValidationError) as error:
                Timesheet(
                    employee=self.user,
                    week_start=date(2026, 10, 20),
                    client=client_record,
                    project=project,
                ).full_clean()
        self.assertIn(
            "The week must start on a Monday.",
            error.exception.message_dict["week_start"],
        )
