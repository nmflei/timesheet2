import secrets

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Q
from django.forms import modelformset_factory
from django.utils.translation import gettext_lazy as _

from .models import Client, DayEntry, EmployeeProfile, Project, Timesheet


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = [
            "company_name",
            "address",
            "postal_code",
            "locality",
            "district",
            "country",
            "tax_number",
            "contact_name",
            "email",
        ]
        widgets = {"address": forms.TextInput()}


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            "client",
            "name",
            "location",
            "approver_name",
            "approver_email",
            "normal_hour_rate",
            "overtime_hour_rate",
            "sunday_hour_rate",
        ]

    def __init__(self, *args, fixed_client=None, **kwargs):
        super().__init__(*args, **kwargs)
        if fixed_client is not None:
            self.fields["client"].queryset = Client.objects.filter(pk=fixed_client.pk)
            self.fields["client"].initial = fixed_client.pk
            self.fields["client"].widget = forms.HiddenInput()


class EmployeeForm(forms.Form):
    name = forms.CharField(label=_("Nome"), max_length=150)
    position = forms.CharField(label=_("Posição"), max_length=120)
    email = forms.EmailField(label=_("Email"), max_length=254)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        self.is_new = instance is None
        super().__init__(*args, **kwargs)
        if instance is not None:
            profile = instance.employee_profile
            self.initial.update(
                name=profile.name,
                position=profile.position,
                email=instance.email,
            )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().casefold()
        users = get_user_model().objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        )
        if self.instance is not None:
            users = users.exclude(pk=self.instance.pk)
        if users.exists():
            raise forms.ValidationError(_("Já existe uma conta com este email."))
        if len(email) > 150:
            raise forms.ValidationError(
                _("O email não pode exceder 150 caracteres porque também será o nome de utilizador.")
            )
        return email

    @transaction.atomic
    def save(self):
        User = get_user_model()
        user = self.instance or User()
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["name"]
        if self.instance is None:
            user.set_password(secrets.token_urlsafe(48))
        user.save()
        EmployeeProfile.objects.update_or_create(
            user=user,
            defaults={
                "name": self.cleaned_data["name"],
                "position": self.cleaned_data["position"],
            },
        )
        return user


class TimesheetAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Email ou nome de utilizador"),
        widget=forms.TextInput(attrs={"autofocus": True}),
    )


class TimesheetCreateForm(forms.ModelForm):
    class Meta:
        model = Timesheet
        fields = ["week_start", "client", "project"]
        widgets = {"week_start": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        client_id = self.data.get("client") or self.initial.get("client")
        if hasattr(client_id, "pk"):
            client_id = client_id.pk
        if str(client_id or "").isdecimal():
            self.fields["project"].queryset = Project.objects.filter(client_id=client_id)
        else:
            self.fields["project"].queryset = Project.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        client = cleaned_data.get("client")
        project = cleaned_data.get("project")
        if client and project and project.client_id != client.id:
            self.add_error("project", _("Selecione um projeto do cliente escolhido."))
        monday = cleaned_data.get("week_start")
        if monday and monday.weekday() != 0:
            self.add_error("week_start", _("A semana tem de começar à segunda-feira."))
        return cleaned_data


class DayEntryForm(forms.ModelForm):
    class Meta:
        model = DayEntry
        fields = ["entry_date", "start_time", "end_time", "break_minutes"]
        widgets = {
            "entry_date": forms.HiddenInput(),
            "start_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "end_time": forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
            "break_minutes": forms.NumberInput(attrs={"min": "0", "step": "1"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["entry_date"].disabled = True


DayEntryFormSet = modelformset_factory(
    DayEntry,
    form=DayEntryForm,
    extra=0,
    can_delete=False,
)


class ReviewForm(forms.Form):
    action = forms.ChoiceField(
        choices=[("approve", _("Aprovar")), ("return", _("Devolver para correção"))],
        widget=forms.HiddenInput(),
    )
    note = forms.CharField(
        label=_("Nota"),
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": _("Nota para o colaborador")}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action") == "return" and not cleaned_data.get("note", "").strip():
            self.add_error("note", _("Indique o motivo da devolução."))
        return cleaned_data
