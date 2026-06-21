from django.contrib import admin

from .models import (
    EnvironmentStandard, EnvironmentRecord,
    Equipment, EquipmentStatusRecord,
    DryingAreaRecord, InspectionRecord
)


@admin.register(EnvironmentStandard)
class EnvironmentStandardAdmin(admin.ModelAdmin):
    list_display = ('herb_name', 'param_type', 'stage', 'min_value', 'max_value', 'unit', 'is_active', 'created_at')
    list_filter = ('param_type', 'stage', 'is_active', 'herb_name')
    search_fields = ('herb_name', 'description')
    ordering = ['herb_name', 'param_type', 'stage']


@admin.register(EnvironmentRecord)
class EnvironmentRecordAdmin(admin.ModelAdmin):
    list_display = ('batch', 'record_time', 'temperature', 'humidity', 'location', 'is_abnormal', 'recorder')
    list_filter = ('is_abnormal', 'record_time', 'location')
    search_fields = ('batch__batch_no', 'batch__herb_name', 'recorder')
    readonly_fields = ('is_abnormal', 'abnormal_details')
    date_hierarchy = 'record_time'
    ordering = ['-record_time']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('equipment_no', 'equipment_name', 'equipment_type', 'model', 'status', 'location')
    list_filter = ('equipment_type', 'status')
    search_fields = ('equipment_no', 'equipment_name', 'model', 'manufacturer')
    ordering = ['equipment_type', 'equipment_no']


@admin.register(EquipmentStatusRecord)
class EquipmentStatusRecordAdmin(admin.ModelAdmin):
    list_display = ('equipment', 'batch', 'record_time', 'running_status', 'is_abnormal', 'operator')
    list_filter = ('is_abnormal', 'running_status', 'record_time')
    search_fields = ('equipment__equipment_no', 'equipment__equipment_name', 'batch__batch_no', 'operator')
    readonly_fields = ('is_abnormal',)
    date_hierarchy = 'record_time'
    ordering = ['-record_time']


@admin.register(DryingAreaRecord)
class DryingAreaRecordAdmin(admin.ModelAdmin):
    list_display = ('batch', 'area_name', 'area_type', 'record_time', 'temperature', 'humidity', 'is_abnormal', 'recorder')
    list_filter = ('is_abnormal', 'area_type', 'record_time')
    search_fields = ('batch__batch_no', 'area_name', 'recorder')
    readonly_fields = ('is_abnormal', 'abnormal_details')
    date_hierarchy = 'record_time'
    ordering = ['-record_time']


@admin.register(InspectionRecord)
class InspectionRecordAdmin(admin.ModelAdmin):
    list_display = ('inspection_type', 'inspection_time', 'batch', 'equipment', 'inspector', 'inspection_result')
    list_filter = ('inspection_type', 'inspection_result', 'inspection_time')
    search_fields = ('inspector', 'batch__batch_no', 'equipment__equipment_no', 'abnormal_description')
    date_hierarchy = 'inspection_time'
    ordering = ['-inspection_time']
