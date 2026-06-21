from django.urls import path

from . import views

app_name = 'herbapp'

urlpatterns = [
    path('', views.BatchListView.as_view(), name='batch_list'),
    path('batch/create/', views.BatchCreateView.as_view(), name='batch_create'),
    path('batch/<int:pk>/', views.BatchDetailView.as_view(), name='batch_detail'),
    path('batch/<int:pk>/round/create/', views.RoundCreateView.as_view(), name='round_create'),
    path('batch/<int:pk>/accept/', views.AcceptanceView.as_view(), name='acceptance'),
    path('batch/<int:pk>/chart/', views.BatchChartView.as_view(), name='batch_chart'),
    path('batch/<int:pk>/assessment/', views.BatchGenerateAssessmentView.as_view(), name='batch_assessment'),
    path('batch/<int:batch_pk>/round/<int:round_no>/check-abnormal/', views.RoundCheckAbnormalApi.as_view(), name='round_check_abnormal'),
    path('batch/<int:batch_pk>/round/<int:round_no>/review/', views.RoundReviewView.as_view(), name='round_review'),

    path('templates/', views.TemplateListView.as_view(), name='template_list'),
    path('template/create/', views.TemplateCreateView.as_view(), name='template_create'),
    path('template/<int:pk>/', views.TemplateDetailView.as_view(), name='template_detail'),
    path('template/<int:pk>/edit/', views.TemplateUpdateView.as_view(), name='template_edit'),
    path('template/<int:pk>/delete/', views.TemplateDeleteView.as_view(), name='template_delete'),
    path('template/<int:pk>/api/', views.TemplateDetailApi.as_view(), name='template_api'),

    path('compare/', views.BatchCompareView.as_view(), name='batch_compare'),
    path('compare/api/', views.BatchCompareApi.as_view(), name='batch_compare_api'),
]
