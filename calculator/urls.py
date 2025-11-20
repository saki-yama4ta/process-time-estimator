from django.urls import path

from . import views

urlpatterns = [
    path("", views.calculator_view, name="calculator"),
    path("api/weight/", views.calculate_weight_view, name="calculate_weight"),
    path("api/removal-time/", views.calculate_removal_time_view, name="calculate_removal_time"),
    path("api/drill-tool/conditions/", views.drill_tool_conditions_view, name="drill_tool_conditions"),
    path("api/drill/process/", views.calculate_drill_process_view, name="calculate_drill_process"),
    path("api/tap/process/", views.calculate_tap_process_view, name="calculate_tap_process"),
]
