from datetime import date, time
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

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

    def test_all_weekend_hours_are_overtime(self):
        entry = DayEntry.objects.create(
            timesheet=self.sheet,
            entry_date=date(2026, 10, 24),
            start_time=time(9),
            end_time=time(13),
            break_minutes=30,
        )
        self.assertEqual(entry.normal_hours, Decimal("0"))
        self.assertEqual(entry.overtime_hours, Decimal("4"))

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
        response = self.client.post(
            reverse("timesheet_review", args=[self.sheet.pk]),
            {"action": "return", "note": "Indique a tarefa realizada."},
        )
        self.assertRedirects(response, reverse("timesheet_detail", args=[self.sheet.pk]))
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.status, Timesheet.Status.RETURNED)
        self.assertEqual(self.sheet.history.latest("created_at").note, "Indique a tarefa realizada.")

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
