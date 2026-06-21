from django import forms
from django.core.exceptions import ValidationError
from django.forms import formset_factory, BaseFormSet

from .models import (
    HerbBatch, ProcessingRound, Acceptance,
    ProcessingStandardTemplate, RoundStandard, BatchQualityAssessment
)


class ProcessingStandardTemplateForm(forms.ModelForm):
    class Meta:
        model = ProcessingStandardTemplate
        fields = ['template_name', 'herb_name', 'total_rounds', 'description', 'is_active']
        widgets = {
            'template_name': forms.TextInput(attrs={'class': 'form-control'}),
            'herb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'total_rounds': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_total_rounds(self):
        total_rounds = self.cleaned_data.get('total_rounds')
        if total_rounds is not None and total_rounds < 1:
            raise forms.ValidationError('总轮次必须大于等于1')
        return total_rounds


class RoundStandardForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].required = False

    class Meta:
        model = RoundStandard
        fields = ['round_no', 'steam_time_min', 'steam_time_max', 'dry_duration_min',
                  'dry_duration_max', 'weight_loss_max', 'required_color']
        widgets = {
            'round_no': forms.NumberInput(attrs={'class': 'form-control round-no-input', 'min': '1'}),
            'steam_time_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1'}),
            'steam_time_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1'}),
            'dry_duration_min': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1'}),
            'dry_duration_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1'}),
            'weight_loss_max': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'required_color': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        round_no = cleaned_data.get('round_no')
        if round_no is None or round_no == '':
            return cleaned_data
        required_fields = ['steam_time_min', 'steam_time_max', 'dry_duration_min',
                           'dry_duration_max', 'weight_loss_max']
        for field_name in required_fields:
            if cleaned_data.get(field_name) is None:
                self.add_error(field_name, '此字段为必填项')
        return cleaned_data


class BaseRoundStandardFormSet(BaseFormSet):
    def clean(self):
        round_nos = set()
        for form in self.forms:
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get('DELETE'):
                continue
            round_no = form.cleaned_data.get('round_no')
            if round_no is None or round_no == '':
                continue
            if form.errors:
                continue
            if round_no in round_nos:
                raise ValidationError(f'轮次序号{round_no}重复，请检查')
            round_nos.add(round_no)

        if round_nos:
            expected = set(range(1, max(round_nos) + 1))
            missing = expected - round_nos
            if missing:
                sorted_missing = sorted(missing)
                raise ValidationError(
                    f'轮次必须从第1轮开始连续填写，缺少第{sorted_missing[0]}轮'
                )


RoundStandardFormSet = formset_factory(
    RoundStandardForm,
    formset=BaseRoundStandardFormSet,
    extra=1,
    can_delete=True
)


class HerbBatchForm(forms.ModelForm):
    class Meta:
        model = HerbBatch
        fields = ['batch_no', 'herb_name', 'template', 'initial_weight', 'required_rounds', 'remark']
        widgets = {
            'batch_no': forms.TextInput(attrs={'class': 'form-control'}),
            'herb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-select', 'id': 'id_template'}),
            'initial_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'required_rounds': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'id': 'id_required_rounds'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template'].required = False
        self.fields['template'].queryset = ProcessingStandardTemplate.objects.filter(is_active=True)
        self.fields['template'].empty_label = '—— 不使用模板（手动配置） ——'

    def clean_initial_weight(self):
        initial_weight = self.cleaned_data.get('initial_weight')
        if initial_weight is not None and initial_weight <= 0:
            raise forms.ValidationError('初始重量必须大于0')
        return initial_weight

    def clean_required_rounds(self):
        required_rounds = self.cleaned_data.get('required_rounds')
        if required_rounds is not None and required_rounds < 1:
            raise forms.ValidationError('规定轮次必须大于等于1')
        return required_rounds


class ProcessingRoundForm(forms.ModelForm):
    class Meta:
        model = ProcessingRound
        fields = ['steam_time', 'dry_duration', 'weight', 'color_rating', 'handling_opinion']
        widgets = {
            'steam_time': forms.NumberInput(attrs={
                'class': 'form-control steam-time-input',
                'step': '0.1', 'min': '0.1',
                'data-field': 'steam_time'
            }),
            'dry_duration': forms.NumberInput(attrs={
                'class': 'form-control dry-duration-input',
                'step': '0.1', 'min': '0.1',
                'data-field': 'dry_duration'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control weight-input',
                'step': '0.01', 'min': '0.01',
                'data-field': 'weight'
            }),
            'color_rating': forms.Select(attrs={
                'class': 'form-select color-rating-input',
                'data-field': 'color_rating'
            }),
            'handling_opinion': forms.Textarea(attrs={
                'class': 'form-control handling-opinion-input',
                'rows': 3,
                'placeholder': '若数据超出标准范围，必须填写处理意见...'
            }),
        }

    def __init__(self, *args, batch=None, **kwargs):
        self.batch = batch
        super().__init__(*args, **kwargs)
        if batch:
            self.instance.batch = batch

    def clean(self):
        cleaned_data = super().clean()
        steam_time = cleaned_data.get('steam_time')
        dry_duration = cleaned_data.get('dry_duration')
        weight = cleaned_data.get('weight')
        color_rating = cleaned_data.get('color_rating')
        handling_opinion = cleaned_data.get('handling_opinion')

        if steam_time is not None and steam_time <= 0:
            self.add_error('steam_time', '蒸制时间必须大于0')

        if dry_duration is not None and dry_duration <= 0:
            self.add_error('dry_duration', '晾晒时长必须大于0')

        if weight is not None:
            if weight <= 0:
                self.add_error('weight', '当前重量必须大于0')
            elif self.batch and weight > self.batch.initial_weight:
                self.add_error('weight', '当前重量不能大于初始重量')

        if self.batch and steam_time and dry_duration and weight and color_rating:
            temp_round = ProcessingRound(
                batch=self.batch,
                round_no=self.batch.get_next_round_no(),
                steam_time=steam_time,
                dry_duration=dry_duration,
                weight=weight,
                color_rating=color_rating,
            )
            is_abnormal, reasons = temp_round.detect_abnormalities()
            if is_abnormal and not handling_opinion:
                self.add_error('handling_opinion', '检测到数据异常，必须填写处理意见')

        return cleaned_data


class RoundReviewForm(forms.ModelForm):
    class Meta:
        model = ProcessingRound
        fields = ['review_status', 'review_result', 'reviewer']
        widgets = {
            'review_status': forms.Select(attrs={'class': 'form-select'}),
            'review_result': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reviewer': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AcceptanceForm(forms.ModelForm):
    class Meta:
        model = Acceptance
        fields = ['result', 'remark']
        widgets = {
            'result': forms.Select(attrs={'class': 'form-select'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class QualityAssessmentForm(forms.ModelForm):
    class Meta:
        model = BatchQualityAssessment
        fields = ['evaluator', 'evaluation_remark']
        widgets = {
            'evaluator': forms.TextInput(attrs={'class': 'form-control'}),
            'evaluation_remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BatchCompareForm(forms.Form):
    batches = forms.ModelMultipleChoiceField(
        queryset=HerbBatch.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='选择对比批次（2-5个）',
        required=True
    )

    def __init__(self, *args, **kwargs):
        herb_name = kwargs.pop('herb_name', None)
        super().__init__(*args, **kwargs)
        qs = HerbBatch.objects.all()
        if herb_name:
            qs = qs.filter(herb_name__icontains=herb_name)
        self.fields['batches'].queryset = qs.order_by('-created_at')

    def clean_batches(self):
        batches = self.cleaned_data.get('batches')
        if batches:
            if len(batches) < 2:
                raise ValidationError('至少选择2个批次进行对比')
            if len(batches) > 5:
                raise ValidationError('最多选择5个批次进行对比')
        return batches
