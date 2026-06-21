from django.contrib import admin

from .models import (
    EquipmentOperationStandard, AcceptanceRuleStandard,
    ChangeRequest, ApprovalRecord, ProcessVersionSnapshot,
    BatchProcessVersionLink, QualityFluctuationAnalysis,
)


@admin.register(EquipmentOperationStandard)
class EquipmentOperationStandardAdmin(admin.ModelAdmin):
    list_display = [
        'pk', 'operation_stage', 'operation_name', 'herb_name',
        'version_code', 'version_status', 'is_current', 'created_at',
    ]
    list_filter = [
        'operation_stage', 'param_severity', 'version_status',
        'is_current', 'equipment_type',
    ]
    search_fields = ['operation_name', 'herb_name', 'version_code', 'key_param_name']
    ordering = ['-created_at']


@admin.register(AcceptanceRuleStandard)
class AcceptanceRuleStandardAdmin(admin.ModelAdmin):
    list_display = [
        'pk', 'rule_name', 'rule_type', 'herb_name',
        'version_code', 'version_status', 'is_current', 'created_at',
    ]
    list_filter = ['rule_type', 'version_status', 'is_current', 'result_if_violated']
    search_fields = ['rule_name', 'herb_name', 'version_code']
    ordering = ['-created_at']


@admin.register(ChangeRequest)
class ChangeRequestAdmin(admin.ModelAdmin):
    list_display = [
        'request_no', 'title', 'standard_type', 'change_type',
        'priority', 'status', 'applicant', 'created_at',
    ]
    list_filter = [
        'standard_type', 'change_type', 'priority', 'status',
    ]
    search_fields = ['request_no', 'title', 'applicant', 'change_reason']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'


@admin.register(ApprovalRecord)
class ApprovalRecordAdmin(admin.ModelAdmin):
    list_display = [
        'pk', 'change_request', 'action', 'reviewer', 'reviewed_at',
    ]
    list_filter = ['action']
    search_fields = ['change_request__request_no', 'reviewer', 'remark']
    ordering = ['-reviewed_at']


@admin.register(ProcessVersionSnapshot)
class ProcessVersionSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        'snapshot_no', 'snapshot_name', 'template_version',
        'is_active', 'created_by', 'created_at',
    ]
    list_filter = ['is_active']
    search_fields = ['snapshot_no', 'snapshot_name', 'template_version']
    ordering = ['-created_at']


@admin.register(BatchProcessVersionLink)
class BatchProcessVersionLinkAdmin(admin.ModelAdmin):
    list_display = [
        'pk', 'batch', 'template_version_at_use', 'linked_at', 'linked_by',
    ]
    search_fields = ['batch__batch_no', 'template_version_at_use']
    ordering = ['-linked_at']


@admin.register(QualityFluctuationAnalysis)
class QualityFluctuationAnalysisAdmin(admin.ModelAdmin):
    list_display = [
        'analysis_no', 'title', 'herb_name', 'overall_trend',
        'stability_change', 'status', 'analyzed_at',
    ]
    list_filter = ['status', 'overall_trend', 'stability_change', 'standard_type']
    search_fields = ['analysis_no', 'title', 'herb_name']
    ordering = ['-created_at']
