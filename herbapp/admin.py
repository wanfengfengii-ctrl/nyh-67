from django.contrib import admin

from .models import (
    HerbBatch, ProcessingRound, Acceptance,
    ProcessingStandardTemplate, RoundStandard, BatchQualityAssessment
)


class ProcessingRoundInline(admin.TabularInline):
    model = ProcessingRound
    extra = 0
    readonly_fields = ['is_abnormal', 'abnormal_reasons', 'record_time']
    fields = ['round_no', 'steam_time', 'dry_duration', 'weight', 'color_rating',
              'is_abnormal', 'review_status', 'reviewer', 'reviewed_at']


class RoundStandardInline(admin.TabularInline):
    model = RoundStandard
    extra = 1


@admin.register(ProcessingStandardTemplate)
class ProcessingStandardTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_name', 'herb_name', 'total_rounds', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['template_name', 'herb_name']
    inlines = [RoundStandardInline]


@admin.register(HerbBatch)
class HerbBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_no', 'herb_name', 'template', 'initial_weight',
                    'required_rounds', 'status', 'created_at']
    list_filter = ['status', 'created_at', 'template']
    search_fields = ['batch_no', 'herb_name']
    inlines = [ProcessingRoundInline]


@admin.register(ProcessingRound)
class ProcessingRoundAdmin(admin.ModelAdmin):
    list_display = ['batch', 'round_no', 'steam_time', 'dry_duration', 'weight',
                    'color_rating', 'is_abnormal', 'review_status', 'record_time']
    list_filter = ['color_rating', 'is_abnormal', 'review_status', 'record_time']
    search_fields = ['batch__batch_no']
    readonly_fields = ['is_abnormal', 'abnormal_reasons']


@admin.register(Acceptance)
class AcceptanceAdmin(admin.ModelAdmin):
    list_display = ['batch', 'result', 'accepted_at']
    list_filter = ['result', 'accepted_at']
    search_fields = ['batch__batch_no']


@admin.register(BatchQualityAssessment)
class BatchQualityAssessmentAdmin(admin.ModelAdmin):
    list_display = ['batch', 'final_score', 'overall_grade', 'total_weight_loss_percent',
                    'abnormal_count', 'evaluator', 'created_at']
    list_filter = ['overall_grade', 'created_at']
    search_fields = ['batch__batch_no']
    readonly_fields = ['total_weight_loss_percent', 'avg_color_score', 'abnormal_count',
                       'abnormal_details', 'steam_time_deviation', 'dry_duration_deviation',
                       'final_score', 'overall_grade']
