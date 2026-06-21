from django.contrib import admin

from .models import HerbBatch, ProcessingRound, Acceptance


class ProcessingRoundInline(admin.TabularInline):
    model = ProcessingRound
    extra = 0


@admin.register(HerbBatch)
class HerbBatchAdmin(admin.ModelAdmin):
    list_display = ['batch_no', 'herb_name', 'initial_weight', 'required_rounds', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['batch_no', 'herb_name']
    inlines = [ProcessingRoundInline]


@admin.register(ProcessingRound)
class ProcessingRoundAdmin(admin.ModelAdmin):
    list_display = ['batch', 'round_no', 'steam_time', 'dry_duration', 'weight', 'color_rating', 'record_time']
    list_filter = ['color_rating', 'record_time']
    search_fields = ['batch__batch_no']


@admin.register(Acceptance)
class AcceptanceAdmin(admin.ModelAdmin):
    list_display = ['batch', 'result', 'accepted_at']
    list_filter = ['result', 'accepted_at']
    search_fields = ['batch__batch_no']
