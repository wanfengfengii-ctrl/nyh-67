from django.urls import path

from . import views

app_name = 'processing'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('warnings/', views.WarningListView.as_view(), name='warning_list'),

    path('env-standards/', views.EnvironmentStandardListView.as_view(), name='env_standard_list'),
    path('env-standard/create/', views.EnvironmentStandardCreateView.as_view(), name='env_standard_create'),
    path('env-standard/<int:pk>/edit/', views.EnvironmentStandardUpdateView.as_view(), name='env_standard_edit'),
    path('env-standard/<int:pk>/delete/', views.EnvironmentStandardDeleteView.as_view(), name='env_standard_delete'),

    path('env-records/', views.EnvironmentRecordListView.as_view(), name='env_record_list'),
    path('env-record/create/', views.EnvironmentRecordCreateView.as_view(), name='env_record_create'),
    path('env-record/<int:pk>/', views.EnvironmentRecordDetailView.as_view(), name='env_record_detail'),
    path('batch/<int:batch_pk>/env-record/create/', views.EnvironmentRecordCreateView.as_view(), name='batch_env_record_create'),
    path('batch/<int:batch_pk>/env-check/', views.EnvironmentRecordCheckApi.as_view(), name='env_check_api'),

    path('equipment/', views.EquipmentListView.as_view(), name='equipment_list'),
    path('equipment/create/', views.EquipmentCreateView.as_view(), name='equipment_create'),
    path('equipment/<int:pk>/', views.EquipmentDetailView.as_view(), name='equipment_detail'),
    path('equipment/<int:pk>/edit/', views.EquipmentUpdateView.as_view(), name='equipment_edit'),
    path('equipment/<int:pk>/delete/', views.EquipmentDeleteView.as_view(), name='equipment_delete'),

    path('equipment-status/', views.EquipmentStatusRecordListView.as_view(), name='equipment_status_list'),
    path('equipment-status/create/', views.EquipmentStatusRecordCreateView.as_view(), name='equipment_status_create'),
    path('equipment-status/<int:pk>/', views.EquipmentStatusRecordDetailView.as_view(), name='equipment_status_detail'),
    path('batch/<int:batch_pk>/equipment-status/create/', views.EquipmentStatusRecordCreateView.as_view(), name='batch_equipment_status_create'),

    path('drying-records/', views.DryingAreaRecordListView.as_view(), name='drying_record_list'),
    path('drying-record/create/', views.DryingAreaRecordCreateView.as_view(), name='drying_record_create'),
    path('drying-record/<int:pk>/', views.DryingAreaRecordDetailView.as_view(), name='drying_record_detail'),
    path('batch/<int:batch_pk>/drying-record/create/', views.DryingAreaRecordCreateView.as_view(), name='batch_drying_record_create'),
    path('batch/<int:batch_pk>/drying-check/', views.DryingAreaRecordCheckApi.as_view(), name='drying_check_api'),

    path('inspections/', views.InspectionRecordListView.as_view(), name='inspection_list'),
    path('inspection/create/', views.InspectionRecordCreateView.as_view(), name='inspection_create'),
    path('inspection/<int:pk>/', views.InspectionRecordDetailView.as_view(), name='inspection_detail'),
    path('inspection/<int:pk>/edit/', views.InspectionRecordUpdateView.as_view(), name='inspection_edit'),

    path('batch/<int:pk>/env-monitoring/', views.BatchEnvMonitoringView.as_view(), name='batch_env_monitoring'),
    path('batch/<int:pk>/env-chart/', views.BatchEnvChartApi.as_view(), name='batch_env_chart_api'),
]
