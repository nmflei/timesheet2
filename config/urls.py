from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy

from .views import ConfiguredPasswordResetView
from timesheets.forms import TimesheetAuthenticationForm


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "conta/entrar/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
            authentication_form=TimesheetAuthenticationForm,
        ),
        name="login",
    ),
    path("conta/sair/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "conta/redefinir-palavra-passe/",
        ConfiguredPasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            subject_template_name="registration/password_reset_subject.txt",
            success_url=reverse_lazy("password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "conta/redefinir-palavra-passe/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "conta/redefinir-palavra-passe/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "conta/redefinir-palavra-passe/concluido/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("", include("timesheets.urls")),
]
