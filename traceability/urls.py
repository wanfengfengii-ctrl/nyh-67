from django.urls import path

from . import views

app_name = 'traceability'

urlpatterns = [
    path('', views.TraceabilityDashboardView.as_view(), name='dashboard'),

    path('batch/<int:pk>/', views.BatchTraceabilityView.as_view(), name='batch_trace'),
    path('batch/<int:pk>/timeline-api/', views.BatchTimelineApi.as_view(), name='batch_timeline_api'),
    path('batch/<int:pk>/trend-api/', views.BatchQualityTrendApi.as_view(), name='batch_trend_api'),

    path('warnings/', views.TraceabilityWarningCenterView.as_view(), name='warning_center'),
    path('warnings/api/', views.WarningCenterApi.as_view(), name='warning_api'),

    path('compare/', views.TraceabilityCompareView.as_view(), name='compare'),
    path('compare/api/', views.TraceabilityCompareApi.as_view(), name='compare_api'),
]
