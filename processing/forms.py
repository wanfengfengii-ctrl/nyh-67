from django import forms
from django.utils import timezone

from .models import (
    EnvironmentStandard, EnvironmentRecord,
    Equipment, EquipmentStatusRecord,
    DryingAreaRecord, InspectionRecord
)


class EnvironmentStandardForm(forms.ModelForm):
    class Meta:
        model = EnvironmentStandard
        fields = ['herb_name', 'param_type', 'stage', 'min_value', 'max_value', 'unit', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class EnvironmentRecordForm(forms.ModelForm):
    class Meta:
        model = EnvironmentRecord
        fields = ['round_no', 'record_time', 'temperature', 'humidity', 'location', 'recorder', 'handling_opinion', 'remark']
        widgets = {
            'record_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'handling_opinion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, batch=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['record_time', 'handling_opinion', 'remark']:
                field.widget.attrs['class'] = 'form-control'
        if batch:
            round_nos = list(batch.rounds.values_list('round_no', flat=True))
            self.fields['round_no'].widget = forms.Select(
                choices=[('', '无')] + [(n, f'第{n}轮') for n in round_nos],
                attrs={'class': 'form-control'}
            )
        self.initial['record_time'] = timezone.now().strftime('%Y-%m-%dT%H:%M')


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            'equipment_no', 'equipment_name', 'equipment_type', 'model', 'manufacturer',
            'purchase_date', 'location', 'status', 'capacity', 'last_maintenance_date',
            'next_maintenance_date', 'description'
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'last_maintenance_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'next_maintenance_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['purchase_date', 'last_maintenance_date', 'next_maintenance_date']:
                field.widget.attrs['class'] = 'form-control'


class EquipmentStatusRecordForm(forms.ModelForm):
    class Meta:
        model = EquipmentStatusRecord
        fields = [
            'round_no', 'equipment', 'record_time', 'running_status', 'operating_params',
            'abnormal_description', 'handling_result', 'operator', 'remark'
        ]
        widgets = {
            'operating_params': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'JSON格式，如：{"pressure": "0.5MPa", "temperature": "120°C"}'}),
        }

    def __init__(self, *args, batch=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name != 'operating_params':
                field.widget.attrs['class'] = 'form-control'
        if batch:
            round_nos = list(batch.rounds.values_list('round_no', flat=True))
            self.fields['round_no'].widget = forms.Select(
                choices=[('', '无')] + [(n, f'第{n}轮') for n in round_nos],
                attrs={'class': 'form-control'}
            )
            self.fields['equipment'].queryset = Equipment.objects.filter(
                status__in=[Equipment.STATUS_NORMAL, Equipment.STATUS_MAINTENANCE]
            )


class DryingAreaRecordForm(forms.ModelForm):
    class Meta:
        model = DryingAreaRecord
        fields = [
            'round_no', 'record_time', 'area_name', 'area_type', 'temperature', 'humidity',
            'light_intensity', 'wind_speed', 'ventilation_condition', 'position_info',
            'handling_opinion', 'recorder', 'remark'
        ]

    def __init__(self, *args, batch=None, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        if batch:
            round_nos = list(batch.rounds.values_list('round_no', flat=True))
            self.fields['round_no'].widget = forms.Select(
                choices=[('', '无')] + [(n, f'第{n}轮') for n in round_nos],
                attrs={'class': 'form-control'}
            )


class InspectionRecordForm(forms.ModelForm):
    class Meta:
        model = InspectionRecord
        fields = [
            'batch', 'equipment', 'inspection_type', 'inspection_time', 'inspector',
            'inspection_items', 'inspection_result', 'abnormal_description',
            'handling_result', 'handling_person', 'handling_time', 'remark'
        ]
        widgets = {
            'inspection_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'handling_time': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'inspection_items': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'JSON数组格式，如：["设备外观", "运行声音", "温度"]'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name not in ['inspection_time', 'handling_time', 'inspection_items']:
                field.widget.attrs['class'] = 'form-control'
        self.initial['inspection_time'] = timezone.now().strftime('%Y-%m-%dT%H:%M')
