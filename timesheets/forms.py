from django import forms
from django.forms import modelformset_factory

from .models import Client, DayEntry, Project, Timesheet


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["company_name", "address", "tax_number", "contact_name", "email"]


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
            self.add_error("project", "Selecione um projeto do cliente escolhido.")
        monday = cleaned_data.get("week_start")
        if monday and monday.weekday() != 0:
            self.add_error("week_start", "A semana tem de começar à segunda-feira.")
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
        choices=[("approve", "Aprovar"), ("return", "Devolver para correção")],
        widget=forms.HiddenInput(),
    )
    note = forms.CharField(
        label="Nota",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Nota para o colaborador"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("action") == "return" and not cleaned_data.get("note", "").strip():
            self.add_error("note", "Indique o motivo da devolução.")
        return cleaned_data
