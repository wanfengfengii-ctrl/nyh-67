from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView
from django.http import JsonResponse
from django.db.models import Q, Count, Avg
from django.utils import timezone
from django.contrib import messages

from herbapp.models import HerbBatch
from .models import (
    EnvironmentStandard, EnvironmentRecord,
    Equipment, EquipmentStatusRecord,
    DryingAreaRecord, InspectionRecord
)
from .forms import (
    EnvironmentStandardForm, EnvironmentRecordForm,
    EquipmentForm, EquipmentStatusRecordForm,
    DryingAreaRecordForm, InspectionRecordForm
)


class DashboardView(TemplateView):
    template_name = 'processing/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_warnings_count'] = (
            EnvironmentRecord.objects.filter(is_abnormal=True, handling_opinion='').count()
            + EquipmentStatusRecord.objects.filter(is_abnormal=True, handling_result='').count()
            + DryingAreaRecord.objects.filter(is_abnormal=True, handling_opinion='').count()
            + InspectionRecord.objects.filter(inspection_result='abnormal', handling_result='').count()
        )
        ctx['env_records_today'] = EnvironmentRecord.objects.filter(
            record_time__date=timezone.now().date()
        ).count()
        ctx['equipment_count'] = Equipment.objects.filter(status='normal').count()
        ctx['inspection_pending'] = InspectionRecord.objects.filter(
            inspection_result='pending'
        ).count()
        ctx['recent_env_records'] = EnvironmentRecord.objects.all()[:10]
        ctx['recent_equipment_records'] = EquipmentStatusRecord.objects.all()[:10]
        ctx['abnormal_env_count'] = EnvironmentRecord.objects.filter(is_abnormal=True).count()
        ctx['abnormal_equipment_count'] = EquipmentStatusRecord.objects.filter(is_abnormal=True).count()
        return ctx


class EnvironmentStandardListView(ListView):
    model = EnvironmentStandard
    template_name = 'processing/env_standard_list.html'
    context_object_name = 'standards'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        herb_name = self.request.GET.get('herb', '')
        param_type = self.request.GET.get('type', '')
        active = self.request.GET.get('active', '')
        if herb_name:
            queryset = queryset.filter(herb_name__icontains=herb_name)
        if param_type:
            queryset = queryset.filter(param_type=param_type)
        if active:
            queryset = queryset.filter(is_active=(active == '1'))
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['herb'] = self.request.GET.get('herb', '')
        ctx['type'] = self.request.GET.get('type', '')
        ctx['active'] = self.request.GET.get('active', '')
        ctx['param_type_choices'] = EnvironmentStandard.PARAM_TYPE_CHOICES
        return ctx


class EnvironmentStandardCreateView(CreateView):
    model = EnvironmentStandard
    form_class = EnvironmentStandardForm
    template_name = 'processing/env_standard_form.html'
    success_url = reverse_lazy('processing:env_standard_list')

    def form_valid(self, form):
        messages.success(self.request, f'环境参数标准创建成功')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = False
        return ctx


class EnvironmentStandardUpdateView(UpdateView):
    model = EnvironmentStandard
    form_class = EnvironmentStandardForm
    template_name = 'processing/env_standard_form.html'
    success_url = reverse_lazy('processing:env_standard_list')

    def form_valid(self, form):
        messages.success(self.request, f'环境参数标准更新成功')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = True
        return ctx


class EnvironmentStandardDeleteView(DeleteView):
    model = EnvironmentStandard
    template_name = 'processing/confirm_delete.html'
    success_url = reverse_lazy('processing:env_standard_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, '环境参数标准已删除')
        return super().delete(request, *args, **kwargs)


class EnvironmentRecordListView(ListView):
    model = EnvironmentRecord
    template_name = 'processing/env_record_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        batch_id = self.request.GET.get('batch', '')
        abnormal = self.request.GET.get('abnormal', '')
        keyword = self.request.GET.get('q', '')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if abnormal:
            queryset = queryset.filter(is_abnormal=(abnormal == '1'))
        if keyword:
            queryset = queryset.filter(
                Q(batch__batch_no__icontains=keyword) |
                Q(batch__herb_name__icontains=keyword) |
                Q(location__icontains=keyword)
            )
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['batch'] = self.request.GET.get('batch', '')
        ctx['abnormal'] = self.request.GET.get('abnormal', '')
        ctx['q'] = self.request.GET.get('q', '')
        ctx['batches'] = HerbBatch.objects.all()
        return ctx


class EnvironmentRecordCreateView(View):
    def get(self, request, batch_pk=None):
        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            form = EnvironmentRecordForm(batch=batch)
            standards = EnvironmentStandard.objects.filter(
                herb_name=batch.herb_name, is_active=True
            )
            return render(request, 'processing/env_record_form.html', {
                'form': form,
                'batch': batch,
                'standards': standards,
            })
        form = EnvironmentRecordForm()
        return render(request, 'processing/env_record_form.html', {
            'form': form,
            'batches': HerbBatch.objects.all(),
        })

    def post(self, request, batch_pk=None):
        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            form = EnvironmentRecordForm(request.POST, batch=batch)
        else:
            form = EnvironmentRecordForm(request.POST)

        if form.is_valid():
            record = form.save(commit=False)
            if batch_pk:
                record.batch = batch
            else:
                batch_id = request.POST.get('batch')
                if batch_id:
                    record.batch = get_object_or_404(HerbBatch, pk=batch_id)
            record.detect_abnormalities()
            record.save()
            if record.is_abnormal:
                messages.warning(request, '环境参数异常，已记录处理意见')
            else:
                messages.success(request, '环境监测记录创建成功')
            if batch_pk:
                return redirect('processing:batch_env_monitoring', pk=batch_pk)
            return redirect('processing:env_record_list')

        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            standards = EnvironmentStandard.objects.filter(
                herb_name=batch.herb_name, is_active=True
            )
            return render(request, 'processing/env_record_form.html', {
                'form': form,
                'batch': batch,
                'standards': standards,
            })
        return render(request, 'processing/env_record_form.html', {
            'form': form,
            'batches': HerbBatch.objects.all(),
        })


class EnvironmentRecordDetailView(DetailView):
    model = EnvironmentRecord
    template_name = 'processing/env_record_detail.html'
    context_object_name = 'record'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['standards'] = EnvironmentStandard.objects.filter(
            herb_name=self.object.batch.herb_name,
            is_active=True
        )
        return ctx


class EnvironmentRecordCheckApi(View):
    def post(self, request, batch_pk):
        batch = get_object_or_404(HerbBatch, pk=batch_pk)
        try:
            temperature = request.POST.get('temperature', '')
            humidity = request.POST.get('humidity', '')
            temperature = float(temperature) if temperature else None
            humidity = float(humidity) if humidity else None
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': '参数无效'})

        temp_record = EnvironmentRecord(
            batch=batch,
            temperature=temperature,
            humidity=humidity,
        )
        is_abnormal, abnormalities = temp_record.detect_abnormalities()

        return JsonResponse({
            'ok': True,
            'is_abnormal': is_abnormal,
            'abnormalities': abnormalities,
        })


class DryingAreaRecordCheckApi(View):
    def post(self, request, batch_pk):
        batch = get_object_or_404(HerbBatch, pk=batch_pk)
        try:
            temperature = request.POST.get('temperature', '')
            humidity = request.POST.get('humidity', '')
            temperature = float(temperature) if temperature else None
            humidity = float(humidity) if humidity else None
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': '参数无效'})

        temp_record = DryingAreaRecord(
            batch=batch,
            temperature=temperature,
            humidity=humidity,
        )
        is_abnormal, abnormalities = temp_record.detect_abnormalities()

        return JsonResponse({
            'ok': True,
            'is_abnormal': is_abnormal,
            'abnormalities': abnormalities,
        })


class EquipmentListView(ListView):
    model = Equipment
    template_name = 'processing/equipment_list.html'
    context_object_name = 'equipments'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.GET.get('q', '')
        equip_type = self.request.GET.get('type', '')
        status = self.request.GET.get('status', '')
        if keyword:
            queryset = queryset.filter(
                Q(equipment_no__icontains=keyword) |
                Q(equipment_name__icontains=keyword) |
                Q(model__icontains=keyword)
            )
        if equip_type:
            queryset = queryset.filter(equipment_type=equip_type)
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['type'] = self.request.GET.get('type', '')
        ctx['status'] = self.request.GET.get('status', '')
        ctx['type_choices'] = Equipment.TYPE_CHOICES
        ctx['status_choices'] = Equipment.STATUS_CHOICES
        return ctx


class EquipmentCreateView(CreateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = 'processing/equipment_form.html'
    success_url = reverse_lazy('processing:equipment_list')

    def form_valid(self, form):
        messages.success(self.request, f'设备「{form.instance.equipment_name}」创建成功')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = False
        return ctx


class EquipmentUpdateView(UpdateView):
    model = Equipment
    form_class = EquipmentForm
    template_name = 'processing/equipment_form.html'
    success_url = reverse_lazy('processing:equipment_list')

    def form_valid(self, form):
        messages.success(self.request, f'设备「{form.instance.equipment_name}」更新成功')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = True
        return ctx


class EquipmentDetailView(DetailView):
    model = Equipment
    template_name = 'processing/equipment_detail.html'
    context_object_name = 'equipment'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_records'] = self.object.status_records.all()[:20]
        ctx['inspection_records'] = self.object.inspection_records.all()[:20]
        ctx['abnormal_count'] = self.object.status_records.filter(is_abnormal=True).count()
        ctx['total_records'] = self.object.status_records.count()
        return ctx


class EquipmentDeleteView(DeleteView):
    model = Equipment
    template_name = 'processing/confirm_delete.html'
    success_url = reverse_lazy('processing:equipment_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        record_count = self.object.status_records.count()
        if record_count > 0:
            messages.error(request, f'该设备已有{record_count}条使用记录，无法删除')
            return redirect('processing:equipment_detail', pk=self.object.pk)
        messages.success(request, '设备已删除')
        return super().delete(request, *args, **kwargs)


class EquipmentStatusRecordListView(ListView):
    model = EquipmentStatusRecord
    template_name = 'processing/equipment_status_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        batch_id = self.request.GET.get('batch', '')
        equipment_id = self.request.GET.get('equipment', '')
        abnormal = self.request.GET.get('abnormal', '')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if abnormal:
            queryset = queryset.filter(is_abnormal=(abnormal == '1'))
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['batch'] = self.request.GET.get('batch', '')
        ctx['equipment'] = self.request.GET.get('equipment', '')
        ctx['abnormal'] = self.request.GET.get('abnormal', '')
        ctx['batches'] = HerbBatch.objects.all()
        ctx['equipments'] = Equipment.objects.all()
        return ctx


class EquipmentStatusRecordCreateView(View):
    def get(self, request, batch_pk=None):
        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            form = EquipmentStatusRecordForm(batch=batch)
            return render(request, 'processing/equipment_status_form.html', {
                'form': form,
                'batch': batch,
            })
        form = EquipmentStatusRecordForm()
        return render(request, 'processing/equipment_status_form.html', {'form': form})

    def post(self, request, batch_pk=None):
        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            form = EquipmentStatusRecordForm(request.POST, batch=batch)
        else:
            form = EquipmentStatusRecordForm(request.POST)

        if form.is_valid():
            record = form.save(commit=False)
            if batch_pk:
                record.batch = batch
            record.detect_abnormalities()
            record.save()
            if record.is_abnormal:
                messages.warning(request, '设备状态异常，已记录处理结果')
            else:
                messages.success(request, '设备状态记录创建成功')
            if batch_pk:
                return redirect('processing:batch_env_monitoring', pk=batch_pk)
            return redirect('processing:equipment_status_list')

        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            return render(request, 'processing/equipment_status_form.html', {
                'form': form,
                'batch': batch,
            })
        return render(request, 'processing/equipment_status_form.html', {'form': form})


class EquipmentStatusRecordDetailView(DetailView):
    model = EquipmentStatusRecord
    template_name = 'processing/equipment_status_detail.html'
    context_object_name = 'record'


class DryingAreaRecordListView(ListView):
    model = DryingAreaRecord
    template_name = 'processing/drying_record_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        batch_id = self.request.GET.get('batch', '')
        area_type = self.request.GET.get('area_type', '')
        abnormal = self.request.GET.get('abnormal', '')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if area_type:
            queryset = queryset.filter(area_type=area_type)
        if abnormal:
            queryset = queryset.filter(is_abnormal=(abnormal == '1'))
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['batch'] = self.request.GET.get('batch', '')
        ctx['area_type'] = self.request.GET.get('area_type', '')
        ctx['abnormal'] = self.request.GET.get('abnormal', '')
        ctx['batches'] = HerbBatch.objects.all()
        ctx['area_type_choices'] = DryingAreaRecord.AREA_TYPE_CHOICES
        return ctx


class DryingAreaRecordCreateView(View):
    def get(self, request, batch_pk=None):
        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            form = DryingAreaRecordForm(batch=batch)
            return render(request, 'processing/drying_record_form.html', {
                'form': form,
                'batch': batch,
            })
        form = DryingAreaRecordForm()
        return render(request, 'processing/drying_record_form.html', {'form': form})

    def post(self, request, batch_pk=None):
        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            form = DryingAreaRecordForm(request.POST, batch=batch)
        else:
            form = DryingAreaRecordForm(request.POST)

        if form.is_valid():
            record = form.save(commit=False)
            if batch_pk:
                record.batch = batch
            record.detect_abnormalities()
            record.save()
            if record.is_abnormal:
                messages.warning(request, '晾晒区域条件异常，已记录处理意见')
            else:
                messages.success(request, '晾晒区域记录创建成功')
            if batch_pk:
                return redirect('processing:batch_env_monitoring', pk=batch_pk)
            return redirect('processing:drying_record_list')

        if batch_pk:
            batch = get_object_or_404(HerbBatch, pk=batch_pk)
            return render(request, 'processing/drying_record_form.html', {
                'form': form,
                'batch': batch,
            })
        return render(request, 'processing/drying_record_form.html', {'form': form})


class DryingAreaRecordDetailView(DetailView):
    model = DryingAreaRecord
    template_name = 'processing/drying_record_detail.html'
    context_object_name = 'record'


class InspectionRecordListView(ListView):
    model = InspectionRecord
    template_name = 'processing/inspection_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        batch_id = self.request.GET.get('batch', '')
        equipment_id = self.request.GET.get('equipment', '')
        inspection_type = self.request.GET.get('type', '')
        result = self.request.GET.get('result', '')
        if batch_id:
            queryset = queryset.filter(batch_id=batch_id)
        if equipment_id:
            queryset = queryset.filter(equipment_id=equipment_id)
        if inspection_type:
            queryset = queryset.filter(inspection_type=inspection_type)
        if result:
            queryset = queryset.filter(inspection_result=result)
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['batch'] = self.request.GET.get('batch', '')
        ctx['equipment'] = self.request.GET.get('equipment', '')
        ctx['type'] = self.request.GET.get('type', '')
        ctx['result'] = self.request.GET.get('result', '')
        ctx['batches'] = HerbBatch.objects.all()
        ctx['equipments'] = Equipment.objects.all()
        ctx['type_choices'] = InspectionRecord.INSPECTION_TYPE_CHOICES
        ctx['result_choices'] = InspectionRecord.RESULT_CHOICES
        return ctx


class InspectionRecordCreateView(CreateView):
    model = InspectionRecord
    form_class = InspectionRecordForm
    template_name = 'processing/inspection_form.html'
    success_url = reverse_lazy('processing:inspection_list')

    def form_valid(self, form):
        record = form.save(commit=False)
        if record.inspection_result == 'abnormal' and not record.handling_time:
            record.handling_time = timezone.now()
        record.save()
        if record.inspection_result == 'abnormal':
            messages.warning(self.request, '巡检发现异常，已记录处理结果')
        else:
            messages.success(self.request, '巡检记录创建成功')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = False
        return ctx


class InspectionRecordDetailView(DetailView):
    model = InspectionRecord
    template_name = 'processing/inspection_detail.html'
    context_object_name = 'record'


class InspectionRecordUpdateView(UpdateView):
    model = InspectionRecord
    form_class = InspectionRecordForm
    template_name = 'processing/inspection_form.html'
    success_url = reverse_lazy('processing:inspection_list')

    def form_valid(self, form):
        record = form.save(commit=False)
        if record.inspection_result == 'abnormal' and not record.handling_time:
            record.handling_time = timezone.now()
        record.save()
        messages.success(self.request, '巡检记录更新成功')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = True
        return ctx


class BatchEnvMonitoringView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        env_records = batch.env_records.all().order_by('-record_time')
        equipment_records = batch.equipment_records.all().order_by('-record_time')
        drying_records = batch.drying_records.all().order_by('-record_time')
        inspection_records = batch.inspection_records.all().order_by('-inspection_time')

        env_abnormal_count = env_records.filter(is_abnormal=True).count()
        equipment_abnormal_count = equipment_records.filter(is_abnormal=True).count()
        drying_abnormal_count = drying_records.filter(is_abnormal=True).count()
        inspection_abnormal_count = inspection_records.filter(inspection_result='abnormal').count()

        return render(request, 'processing/batch_env_monitoring.html', {
            'batch': batch,
            'env_records': env_records,
            'equipment_records': equipment_records,
            'drying_records': drying_records,
            'inspection_records': inspection_records,
            'env_abnormal_count': env_abnormal_count,
            'equipment_abnormal_count': equipment_abnormal_count,
            'drying_abnormal_count': drying_abnormal_count,
            'inspection_abnormal_count': inspection_abnormal_count,
            'total_abnormal_count': env_abnormal_count + equipment_abnormal_count + drying_abnormal_count + inspection_abnormal_count,
        })


class BatchEnvChartApi(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        env_records = batch.env_records.all().order_by('record_time')

        labels = []
        temp_data = []
        hum_data = []
        abnormal_flags = []

        for r in env_records:
            labels.append(r.record_time.strftime('%m-%d %H:%M'))
            temp_data.append(float(r.temperature) if r.temperature else None)
            hum_data.append(float(r.humidity) if r.humidity else None)
            if r.is_abnormal:
                abnormal_flags.append({
                    'index': len(labels) - 1,
                    'details': r.abnormal_details if isinstance(r.abnormal_details, dict) else {},
                    'handling': r.handling_opinion or '',
                })

        standards = EnvironmentStandard.objects.filter(
            herb_name=batch.herb_name, is_active=True
        )
        standard_data = {}
        for s in standards:
            key = f'{s.param_type}_{s.stage}'
            standard_data[key] = {
                'min': float(s.min_value),
                'max': float(s.max_value),
                'unit': s.unit,
                'display': s.get_param_type_display(),
            }

        equipment_stats = batch.equipment_records.values('equipment__equipment_no', 'equipment__equipment_name').annotate(
            total=Count('id'),
            abnormal=Count('id', filter=Q(is_abnormal=True))
        )

        inspection_stats = {
            'total': batch.inspection_records.count(),
            'normal': batch.inspection_records.filter(inspection_result='normal').count(),
            'abnormal': batch.inspection_records.filter(inspection_result='abnormal').count(),
            'pending': batch.inspection_records.filter(inspection_result='pending').count(),
        }

        drying_records = batch.drying_records.all().order_by('record_time')
        drying_labels = []
        drying_temp = []
        drying_hum = []
        for r in drying_records:
            drying_labels.append(r.record_time.strftime('%m-%d %H:%M'))
            drying_temp.append(float(r.temperature) if r.temperature else None)
            drying_hum.append(float(r.humidity) if r.humidity else None)

        return JsonResponse({
            'batch_no': batch.batch_no,
            'herb_name': batch.herb_name,
            'env_chart': {
                'labels': labels,
                'temperature': temp_data,
                'humidity': hum_data,
                'abnormal_flags': abnormal_flags,
            },
            'drying_chart': {
                'labels': drying_labels,
                'temperature': drying_temp,
                'humidity': drying_hum,
            },
            'standards': standard_data,
            'equipment_stats': list(equipment_stats),
            'inspection_stats': inspection_stats,
        })


class WarningListView(ListView):
    template_name = 'processing/warning_list.html'
    context_object_name = 'warnings'
    paginate_by = 30

    def get_queryset(self):
        warnings = []

        env_records = EnvironmentRecord.objects.filter(is_abnormal=True).order_by('-record_time')
        for r in env_records:
            warnings.append({
                'type': 'env',
                'type_display': '环境异常',
                'time': r.record_time,
                'batch': r.batch,
                'description': '; '.join(r.abnormal_details.values()) if isinstance(r.abnormal_details, dict) else str(r.abnormal_details),
                'handling': r.handling_opinion,
                'has_handling': bool(r.handling_opinion),
                'url': reverse('processing:env_record_detail', kwargs={'pk': r.pk}),
            })

        equip_records = EquipmentStatusRecord.objects.filter(is_abnormal=True).order_by('-record_time')
        for r in equip_records:
            warnings.append({
                'type': 'equipment',
                'type_display': '设备异常',
                'time': r.record_time,
                'batch': r.batch,
                'equipment': r.equipment,
                'description': r.abnormal_description or '设备状态异常',
                'handling': r.handling_result,
                'has_handling': bool(r.handling_result),
                'url': reverse('processing:equipment_status_detail', kwargs={'pk': r.pk}),
            })

        drying_records = DryingAreaRecord.objects.filter(is_abnormal=True).order_by('-record_time')
        for r in drying_records:
            warnings.append({
                'type': 'drying',
                'type_display': '晾晒区异常',
                'time': r.record_time,
                'batch': r.batch,
                'description': '; '.join(r.abnormal_details.values()) if isinstance(r.abnormal_details, dict) else str(r.abnormal_details),
                'handling': r.handling_opinion,
                'has_handling': bool(r.handling_opinion),
                'url': reverse('processing:drying_record_detail', kwargs={'pk': r.pk}),
            })

        inspection_records = InspectionRecord.objects.filter(
            inspection_result='abnormal'
        ).order_by('-inspection_time')
        for r in inspection_records:
            warnings.append({
                'type': 'inspection',
                'type_display': '巡检异常',
                'time': r.inspection_time,
                'batch': r.batch,
                'equipment': r.equipment,
                'description': r.abnormal_description or '',
                'handling': r.handling_result,
                'has_handling': bool(r.handling_result),
                'url': reverse('processing:inspection_detail', kwargs={'pk': r.pk}),
            })

        warnings.sort(key=lambda x: x['time'], reverse=True)
        return warnings

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        pending = [w for w in self.get_queryset() if not w['has_handling']]
        ctx['pending_count'] = len(pending)
        ctx['handled_count'] = len(self.get_queryset()) - len(pending)
        return ctx
