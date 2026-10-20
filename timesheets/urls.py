from django.urls import path

from . import views


urlpatterns = [
    path("idioma/", views.set_language, name="set_language"),
    path("", views.dashboard, name="dashboard"),
    path("clientes/", views.client_list, name="client_list"),
    path("clientes/novo/", views.client_create, name="client_create"),
    path("clientes/<int:pk>/", views.client_detail, name="client_detail"),
    path("clientes/<int:pk>/editar/", views.client_edit, name="client_edit"),
    path("projetos/", views.project_list, name="project_list"),
    path("projetos/novo/", views.project_create, name="project_create"),
    path("clientes/<int:pk>/projetos/novo/", views.project_create_for_client, name="project_create_for_client"),
    path("projetos/<int:pk>/editar/", views.project_edit, name="project_edit"),
    path("colaboradores/", views.employee_list, name="employee_list"),
    path("colaboradores/novo/", views.employee_create, name="employee_create"),
    path("colaboradores/<int:pk>/editar/", views.employee_edit, name="employee_edit"),
    path("colaboradores/<int:pk>/estado/", views.employee_toggle_active, name="employee_toggle_active"),
    path("api/clientes/<int:client_id>/projetos/", views.projects_for_client, name="projects_for_client"),
    path("folhas/nova/", views.timesheet_create, name="timesheet_create"),
    path("folhas/<int:pk>/", views.timesheet_detail, name="timesheet_detail"),
    path("folhas/<int:pk>/submeter/", views.timesheet_submit, name="timesheet_submit"),
    path("aprovacoes/", views.approval_list, name="approval_list"),
    path("aprovacoes/<int:pk>/decidir/", views.timesheet_review, name="timesheet_review"),
]
