from django.urls import path

from . import views

app_name = 'version_control'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),

    path('changes/', views.ChangeRequestListView.as_view(), name='change_list'),
    path('change/create/', views.ChangeRequestCreateView.as_view(), name='change_create'),
    path('change/<int:pk>/', views.ChangeRequestDetailView.as_view(), name='change_detail'),
    path('change/<int:pk>/submit/', views.ChangeRequestSubmitView.as_view(), name='change_submit'),
    path('change/<int:pk>/cancel/', views.ChangeRequestCancelView.as_view(), name='change_cancel'),
    path('change/<int:pk>/review/', views.ChangeRequestReviewView.as_view(), name='change_review'),
    path('change/<int:pk>/publish/', views.ChangeRequestPublishView.as_view(), name='change_publish'),

    path('version-compare/', views.VersionCompareView.as_view(), name='version_compare'),
    path('standard-history/', views.StandardHistoryView.as_view(), name='standard_history'),

    path('batch-version/', views.BatchVersionView.as_view(), name='batch_version'),
    path('batch-link/', views.LinkBatchToVersionView.as_view(), name='batch_link'),

    path('equipment-ops/', views.EquipmentOpListView.as_view(), name='equipment_op_list'),
    path('equipment-op/create/', views.EquipmentOpCreateView.as_view(), name='equipment_op_create'),
    path('equipment-op/<int:pk>/', views.EquipmentOpDetailView.as_view(), name='equipment_op_detail'),

    path('acceptance-rules/', views.AcceptanceRuleListView.as_view(), name='acceptance_rule_list'),
    path('acceptance-rule/create/', views.AcceptanceRuleCreateView.as_view(), name='acceptance_rule_create'),
    path('acceptance-rule/<int:pk>/', views.AcceptanceRuleDetailView.as_view(), name='acceptance_rule_detail'),

    path('snapshots/', views.SnapshotListView.as_view(), name='snapshot_list'),
    path('snapshot/create/', views.SnapshotCreateView.as_view(), name='snapshot_create'),
    path('snapshot/<int:pk>/', views.SnapshotDetailView.as_view(), name='snapshot_detail'),

    path('quality-analyses/', views.QualityAnalysisListView.as_view(), name='quality_list'),
    path('quality/create/', views.QualityAnalysisCreateView.as_view(), name='quality_create'),
    path('quality/<int:pk>/', views.QualityAnalysisDetailView.as_view(), name='quality_detail'),
    path('quality/<int:pk>/run/', views.QualityAnalysisRunView.as_view(), name='quality_run'),
    path('quality/<int:pk>/review/', views.QualityAnalysisReviewView.as_view(), name='quality_review'),
]
