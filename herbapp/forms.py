from django import forms
from django.core.exceptions import ValidationError

from .models import HerbBatch, ProcessingRound, Acceptance


class HerbBatchForm(forms.ModelForm):
    class Meta:
        model = HerbBatch
        fields = ['batch_no', 'herb_name', 'initial_weight', 'required_rounds', 'remark']
        widgets = {
            'batch_no': forms.TextInput(attrs={'class': 'form-control'}),
            'herb_name': forms.TextInput(attrs={'class': 'form-control'}),
            'initial_weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'required_rounds': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ProcessingRoundForm(forms.ModelForm):
    class Meta:
        model = ProcessingRound
        fields = ['steam_time', 'dry_duration', 'weight', 'color_rating', 'handling_opinion']
        widgets = {
            'steam_time': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1'}),
            'dry_duration': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'min': '0.1'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'color_rating': forms.Select(attrs={'class': 'form-select'}),
            'handling_opinion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
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

        if weight is not None and self.batch and weight > self.batch.initial_weight:
            self.add_error('weight', '当前重量不能大于初始重量')

        if color_rating == ProcessingRound.COLOR_ABNORMAL and not handling_opinion:
            self.add_error('handling_opinion', '色泽评级异常时必须填写处理意见')

        return cleaned_data


class AcceptanceForm(forms.ModelForm):
    class Meta:
        model = Acceptance
        fields = ['result', 'remark']
        widgets = {
            'result': forms.Select(attrs={'class': 'form-select'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
