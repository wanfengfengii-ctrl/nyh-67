from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    ChangeRequest, EquipmentOperationStandard, AcceptanceRuleStandard,
    QualityFluctuationAnalysis, ApprovalRecord,
)


class ChangeRequestForm(forms.ModelForm):
    class Meta:
        model = ChangeRequest
        fields = [
            'standard_type', 'change_type', 'priority',
            'source_standard_id', 'source_version_code',
            'title', 'change_reason', 'impact_scope', 'expected_effect',
            'risk_assessment', 'rollback_plan',
            'applicant', 'department', 'effective_date', 'obsolescence_date',
        ]
        widgets = {
            'standard_type': forms.Select(attrs={'class': 'form-control'}),
            'change_type': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'source_standard_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'source_version_code': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'change_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'impact_scope': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'expected_effect': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'risk_assessment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rollback_plan': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'applicant': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'effective_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'obsolescence_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'source_standard_id': '原标准ID',
            'source_version_code': '原版本号',
        }

    def clean(self):
        cleaned_data = super().clean()
        change_type = cleaned_data.get('change_type')
        source_id = cleaned_data.get('source_standard_id')
        if change_type != ChangeRequest.CHANGE_TYPE_CREATE and not source_id:
            raise ValidationError({'source_standard_id': '修改/废弃标准必须指定原标准ID'})
        return cleaned_data


class ChangeRequestReviewForm(forms.Form):
    ACTION_CHOICES = [
        ('approve', '审核通过'),
        ('reject', '审核驳回'),
        ('comment', '添加备注'),
    ]
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    reviewer = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    remark = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        label='审核意见'
    )


class ChangeRequestPublishForm(forms.Form):
    publisher = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='发布人'
    )
    publish_remark = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='发布备注'
    )
    effective_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='生效日期'
    )


class EquipmentOperationStandardForm(forms.ModelForm):
    class Meta:
        model = EquipmentOperationStandard
        exclude = [
            'version_created_at', 'created_at', 'updated_at',
        ]
        widgets = {
            'equipment': forms.Select(attrs={'class': 'form-control'}),
            'equipment_type': forms.Select(attrs={'class': 'form-control'}),
            'herb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'operation_stage': forms.Select(attrs={'class': 'form-control'}),
            'operation_name': forms.TextInput(attrs={'class': 'form-control'}),
            'operation_steps': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'key_param_name': forms.TextInput(attrs={'class': 'form-control'}),
            'key_param_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'key_param_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'key_param_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'param_severity': forms.Select(attrs={'class': 'form-control'}),
            'safety_requirements': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'quality_checkpoints': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tolerance_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'version_code': forms.TextInput(attrs={'class': 'form-control'}),
            'version_major': forms.NumberInput(attrs={'class': 'form-control'}),
            'version_minor': forms.NumberInput(attrs={'class': 'form-control'}),
            'version_status': forms.Select(attrs={'class': 'form-control'}),
            'master_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'version_remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'version_created_by': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AcceptanceRuleStandardForm(forms.ModelForm):
    class Meta:
        model = AcceptanceRuleStandard
        exclude = [
            'version_created_at', 'created_at', 'updated_at',
        ]
        widgets = {
            'rule_name': forms.TextInput(attrs={'class': 'form-control'}),
            'rule_type': forms.Select(attrs={'class': 'form-control'}),
            'herb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'rule_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'threshold_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'threshold_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'result_if_violated': forms.Select(attrs={'class': 'form-control'}),
            'weight_in_comprehensive': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'handling_advice': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reference_standard': forms.TextInput(attrs={'class': 'form-control'}),
            'version_code': forms.TextInput(attrs={'class': 'form-control'}),
            'version_major': forms.NumberInput(attrs={'class': 'form-control'}),
            'version_minor': forms.NumberInput(attrs={'class': 'form-control'}),
            'version_status': forms.Select(attrs={'class': 'form-control'}),
            'master_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'version_remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'version_created_by': forms.TextInput(attrs={'class': 'form-control'}),
        }


class QualityFluctuationAnalysisForm(forms.ModelForm):
    class Meta:
        model = QualityFluctuationAnalysis
        fields = [
            'title', 'related_change_request', 'standard_type', 'standard_id',
            'herb_name', 'before_version', 'after_version',
            'before_start_date', 'before_end_date',
            'after_start_date', 'after_end_date',
            'analysis_conclusion', 'improvement_suggestions', 'statistical_notes',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 200}),
            'related_change_request': forms.Select(attrs={'class': 'form-control'}),
            'standard_type': forms.Select(attrs={'class': 'form-control'}),
            'standard_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'herb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'before_version': forms.TextInput(attrs={'class': 'form-control'}),
            'after_version': forms.TextInput(attrs={'class': 'form-control'}),
            'before_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'before_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'after_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'after_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'analysis_conclusion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'improvement_suggestions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'statistical_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class QualityReviewForm(forms.Form):
    reviewed_by = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label='复核人'
    )
    review_remark = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='复核意见'
    )


class VersionCompareForm(forms.Form):
    standard_type = forms.ChoiceField(
        choices=[
            ('', '请选择标准类型'),
            ('processing_template', '炮制标准模板'),
            ('environment_standard', '环境参数标准'),
            ('equipment_operation', '设备操作要求'),
            ('acceptance_rule', '验收规则'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        required=False
    )
    master_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='主记录ID'
    )
    version_left = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '版本号，如 V1.0'}),
        label='左侧版本号',
        required=False
    )
    version_right = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '版本号，如 V2.0'}),
        label='右侧版本号',
        required=False
    )
    id_left = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='左侧记录ID'
    )
    id_right = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='右侧记录ID'
    )
