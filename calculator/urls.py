from django.urls import path

from . import views

urlpatterns = [
    path("", views.calculator_view, name="calculator"),
    path("api/weight/", views.calculate_weight_view, name="calculate_weight"),
    path("api/removal-time/", views.calculate_removal_time_view, name="calculate_removal_time"),
    path("api/drill-tool/conditions/", views.drill_tool_conditions_view, name="drill_tool_conditions"),
    path("api/drill/process/", views.calculate_drill_process_view, name="calculate_drill_process"),
    path("api/tap/process/", views.calculate_tap_process_view, name="calculate_tap_process"),
    path("api/endmill/circle/", views.calculate_endmill_circle_view, name="calculate_endmill_circle"),
    path("api/endmill/side/", views.calculate_endmill_side_view, name="calculate_endmill_side"),
    path("api/endmill/slot/", views.calculate_endmill_slot_view, name="calculate_endmill_slot"),
    path("api/boring/process/", views.calculate_boring_process_view, name="calculate_boring_process"),
    path("api/reamer/process/", views.calculate_reamer_process_view, name="calculate_reamer_process"),
    path("api/counterbore/process/", views.calculate_counterbore_process_view, name="calculate_counterbore_process"),
    path("api/milling/process/", views.calculate_milling_process_view, name="calculate_milling_process"),
    path("api/chamfer/circle/", views.calculate_chamfer_circle_view, name="calculate_chamfer_circle"),
    path("api/chamfer/side/", views.calculate_chamfer_side_view, name="calculate_chamfer_side"),
]
