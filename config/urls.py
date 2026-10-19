from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("conta/entrar/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("conta/sair/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("timesheets.urls")),
]
