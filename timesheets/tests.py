from datetime import date, time
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from .forms import ClientForm, TimesheetCreateForm
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


class ClientManagementTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_user(
            username="manager", password="test-password", email="manager@example.pt", is_staff=True
        )
        self.client_record = Client.objects.create(
            company_name="Cliente Exemplo",
            address="Rua da Empresa, 12",
            tax_number="501234567",
            contact_name="Ana Contacto",
            email="ana@example.pt",
            postal_code="1250-096",
            locality="Lisboa",
            district="Lisboa",
            country="Portugal",
        )
        self.project = Project.objects.create(
            client=self.client_record,
            name="Projeto Lisboa",
            location="Lisboa",
            approver_name="Rui",
            approver_email="rui@example.pt",
        )
        self.client.force_login(self.manager)

    def test_client_form_uses_single_line_address_and_accepts_structured_address(self):
        form = ClientForm(
            data={
                "company_name": "Novo Cliente",
                "address": "Avenida da Liberdade, 10",
                "postal_code": "1250-096",
                "locality": "Lisboa",
                "district": "Lisboa",
                "country": "Portugal",
                "tax_number": "509876543",
                "contact_name": "Joana",
                "email": "joana@example.pt",
            }
        )
        self.assertEqual(form.fields["address"].widget.__class__.__name__, "TextInput")
        self.assertTrue(form.is_valid(), form.errors)
        client_record = form.save()
        self.assertEqual(client_record.postal_code, "1250-096")
        self.assertEqual(client_record.locality, "Lisboa")
        self.assertEqual(client_record.district, "Lisboa")
        self.assertEqual(client_record.country, "Portugal")

        response = self.client.get(reverse("client_edit", args=[self.client_record.pk]))
        self.assertContains(response, 'type="text" name="address"')
        self.assertNotContains(response, '<textarea name="address"')

    def test_client_detail_lists_associated_projects_and_address(self):
        response = self.client.get(reverse("client_detail", args=[self.client_record.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Projetos associados")
        self.assertContains(response, "Projeto Lisboa")
        self.assertContains(response, "Rua da Empresa, 12")
        self.assertContains(response, "1250-096")

    def test_client_list_visibly_renders_associated_project_names_in_portuguese(self):
        response = self.client.get(reverse("client_list"))
        self.assertContains(response, "Projetos associados")
        self.assertContains(response, "Projeto Lisboa")
        self.assertContains(response, 'class="associated-project-list"')
        self.assertContains(response, reverse("project_edit", args=[self.project.pk]))

    def test_client_list_visibly_renders_associated_project_names_in_english(self):
        self.client.cookies["timesheet_language"] = "en"
        response = self.client.get(reverse("client_list"))
        self.assertContains(response, "Associated projects")
        self.assertContains(response, "Projeto Lisboa")
        self.assertContains(response, 'class="associated-project-list"')

    def test_client_detail_shows_empty_projects_message(self):
        client_without_projects = Client.objects.create(
            company_name="Sem projetos",
            address="Rua Nova, 1",
            tax_number="509876544",
            contact_name="Contacto",
            email="contacto@example.pt",
        )
        response = self.client.get(reverse("client_detail", args=[client_without_projects.pk]))
        self.assertContains(response, "Este cliente ainda não tem projetos associados.")

    def test_client_form_translates_structured_address_fields(self):
        self.client.cookies["timesheet_language"] = "en"
        response = self.client.get(reverse("client_edit", args=[self.client_record.pk]))
        self.assertContains(response, "Full address")
        self.assertContains(response, "Postcode")
        self.assertContains(response, "Locality")
        self.assertContains(response, "District")
        self.assertContains(response, "Country")

    def test_non_manager_cannot_view_client_detail(self):
        employee = get_user_model().objects.create_user(
            username="employee", password="test-password", email="employee@example.pt"
        )
        self.client.force_login(employee)
        response = self.client.get(reverse("client_detail", args=[self.client_record.pk]))
        self.assertEqual(response.status_code, 403)


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
        self.client.force_login(self.approver)
        self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("timesheet_detail", args=[self.sheet.pk])},
        )
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


class LanguageSelectionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="language-user", password="safe-password", email="language@example.pt"
        )

    def test_authenticated_user_defaults_to_portuguese(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "pt-pt")

    def test_authenticated_language_choice_is_temporary_for_current_browser_session(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("dashboard")},
        )
        self.assertRedirects(response, reverse("dashboard"))
        language_cookie = response.cookies["timesheet_language"]
        self.assertEqual(language_cookie.value, "en")
        self.assertEqual(language_cookie["max-age"], "")
        self.assertEqual(language_cookie["expires"], "")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME]["max-age"], 0)

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

    def test_language_choice_does_not_carry_over_to_a_new_browser_session(self):
        another_session = self.client_class()
        another_session.force_login(self.user)
        another_session.cookies[settings.LANGUAGE_COOKIE_NAME] = "en"
        response = another_session.get(reverse("login"))
        self.assertEqual(response.wsgi_request.LANGUAGE_CODE, "pt-pt")
        self.assertContains(response, "Entrar")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME]["max-age"], 0)

    def test_anonymous_language_choice_uses_a_session_only_cookie(self):
        response = self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("login")},
        )
        self.assertRedirects(response, reverse("login"))
        language_cookie = response.cookies["timesheet_language"]
        self.assertEqual(language_cookie["max-age"], "")
        self.assertEqual(language_cookie["expires"], "")
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME]["max-age"], 0)
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
        response = self.client.post(reverse("set_language"), {"language": "fr", "next": "/"})
        self.assertNotIn("timesheet_language", response.cookies)
        self.assertEqual(self.client.get(reverse("dashboard")).wsgi_request.LANGUAGE_CODE, "pt-pt")

    def test_admin_uses_session_language_and_shows_language_selector(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-language", password="safe-password", email="admin@example.pt"
        )
        self.client.force_login(admin)
        self.client.post(
            reverse("set_language"),
            {"language": "en", "next": reverse("admin:index")},
        )
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
        self.client.post(
            reverse("set_language"),
            {"language": "pt-pt", "next": reverse("admin:index")},
        )
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
            messages = [str(message) for message in error.exception.message_dict["week_start"]]
        self.assertIn(
            "The week must start on a Monday.",
            messages,
        )
