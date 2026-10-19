# Generated for the initial timesheet application schema.
import django.conf
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(django.conf.settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Client",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("company_name", models.CharField(max_length=180, verbose_name="nome da empresa")),
                ("address", models.TextField(verbose_name="morada completa")),
                ("tax_number", models.CharField(max_length=20, unique=True, verbose_name="NIF")),
                ("contact_name", models.CharField(max_length=160, verbose_name="nome do contacto")),
                ("email", models.EmailField(max_length=254, verbose_name="email")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
            ],
            options={"verbose_name": "cliente", "verbose_name_plural": "clientes", "ordering": ["company_name"]},
        ),
        migrations.CreateModel(
            name="Project",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180, verbose_name="nome do projeto")),
                ("location", models.CharField(max_length=240, verbose_name="localização")),
                ("approver_name", models.CharField(max_length=160, verbose_name="responsável pela aprovação")),
                ("approver_email", models.EmailField(max_length=254, verbose_name="email do responsável")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="criado em")),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="projects", to="timesheets.client", verbose_name="cliente")),
            ],
            options={"verbose_name": "projeto", "verbose_name_plural": "projetos", "ordering": ["client__company_name", "name"]},
        ),
        migrations.CreateModel(
            name="Timesheet",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("week_start", models.DateField(verbose_name="segunda-feira da semana")),
                ("status", models.CharField(choices=[("draft", "Rascunho"), ("submitted", "Submetida"), ("approved", "Aprovada"), ("returned", "Devolvida")], default="draft", max_length=12, verbose_name="estado")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="criada em")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="atualizada em")),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="timesheets.client", verbose_name="cliente")),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="timesheets", to=django.conf.settings.AUTH_USER_MODEL, verbose_name="colaborador")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="timesheets.project", verbose_name="projeto")),
            ],
            options={"verbose_name": "folha de horas", "verbose_name_plural": "folhas de horas", "ordering": ["-week_start", "-created_at"]},
        ),
        migrations.CreateModel(
            name="DayEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_date", models.DateField(verbose_name="dia")),
                ("start_time", models.TimeField(blank=True, null=True, verbose_name="início")),
                ("end_time", models.TimeField(blank=True, null=True, verbose_name="fim")),
                ("break_minutes", models.PositiveSmallIntegerField(default=0, verbose_name="pausa (minutos)")),
                ("timesheet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="entries", to="timesheets.timesheet", verbose_name="folha")),
            ],
            options={"verbose_name": "registo diário", "verbose_name_plural": "registos diários", "ordering": ["entry_date"]},
        ),
        migrations.CreateModel(
            name="TimesheetHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("draft", "Rascunho"), ("submitted", "Submetida"), ("approved", "Aprovada"), ("returned", "Devolvida")], max_length=12, verbose_name="estado")),
                ("note", models.TextField(blank=True, verbose_name="nota")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="data")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=django.conf.settings.AUTH_USER_MODEL, verbose_name="utilizador")),
                ("timesheet", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="history", to="timesheets.timesheet", verbose_name="folha")),
            ],
            options={"verbose_name": "registo de estado", "verbose_name_plural": "histórico de estados", "ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="project",
            constraint=models.UniqueConstraint(fields=("client", "name"), name="unique_project_name_per_client"),
        ),
        migrations.AddConstraint(
            model_name="timesheet",
            constraint=models.UniqueConstraint(fields=("employee", "week_start", "client", "project"), name="unique_employee_week_client_project"),
        ),
        migrations.AddConstraint(
            model_name="dayentry",
            constraint=models.UniqueConstraint(fields=("timesheet", "entry_date"), name="unique_entry_per_day"),
        ),
    ]
