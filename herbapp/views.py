from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView, TemplateView
from django.http import JsonResponse, HttpResponseRedirect
from django.db.models import Q, Avg, Count
from django.utils import timezone
from django.contrib import messages
from django.forms import modelformset_factory

from .models import (
    HerbBatch, ProcessingRound, Acceptance,
    ProcessingStandardTemplate, RoundStandard, BatchQualityAssessment
)
from .forms import (
    HerbBatchForm, ProcessingRoundForm, AcceptanceForm,
    ProcessingStandardTemplateForm, RoundStandardForm,
    RoundStandardFormSet, RoundReviewForm, QualityAssessmentForm,
    BatchCompareForm
)


class TemplateListView(ListView):
    model = ProcessingStandardTemplate
    template_name = 'herbapp/template_list.html'
    context_object_name = 'templates'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.GET.get('q', '')
        herb_name = self.request.GET.get('herb', '')
        active = self.request.GET.get('active', '')
        if keyword:
            queryset = queryset.filter(
                Q(template_name__icontains=keyword) | Q(herb_name__icontains=keyword)
            )
        if herb_name:
            queryset = queryset.filter(herb_name__icontains=herb_name)
        if active:
            queryset = queryset.filter(is_active=(active == '1'))
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['herb'] = self.request.GET.get('herb', '')
        ctx['active'] = self.request.GET.get('active', '')
        return ctx


class TemplateCreateView(View):
    def get(self, request):
        form = ProcessingStandardTemplateForm()
        formset = RoundStandardFormSet()
        return render(request, 'herbapp/template_form.html', {
            'form': form,
            'formset': formset,
            'is_edit': False,
        })

    def post(self, request):
        form = ProcessingStandardTemplateForm(request.POST)
        formset = RoundStandardFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            template = form.save()
            for f in formset:
                if f.cleaned_data and not f.cleaned_data.get('DELETE'):
                    rs = f.save(commit=False)
                    rs.template = template
                    rs.save()
            messages.success(request, f'标准模板「{template.template_name}」创建成功')
            return redirect('herbapp:template_list')

        return render(request, 'herbapp/template_form.html', {
            'form': form,
            'formset': formset,
            'is_edit': False,
        })


class TemplateUpdateView(View):
    def get(self, request, pk):
        template = get_object_or_404(ProcessingStandardTemplate, pk=pk)
        form = ProcessingStandardTemplateForm(instance=template)
        existing = template.round_standards.all().order_by('round_no')
        initial_data = [{'round_no': r.round_no,
                         'steam_time_min': r.steam_time_min,
                         'steam_time_max': r.steam_time_max,
                         'dry_duration_min': r.dry_duration_min,
                         'dry_duration_max': r.dry_duration_max,
                         'weight_loss_max': r.weight_loss_max,
                         'required_color': r.required_color} for r in existing]
        EditableFormSet = formset_factory(
            RoundStandardForm,
            formset=RoundStandardFormSet.formset,
            extra=1,
            can_delete=True
        )
        formset = EditableFormSet(initial=initial_data)
        return render(request, 'herbapp/template_form.html', {
            'form': form,
            'formset': formset,
            'is_edit': True,
            'template': template,
        })

    def post(self, request, pk):
        template = get_object_or_404(ProcessingStandardTemplate, pk=pk)
        form = ProcessingStandardTemplateForm(request.POST, instance=template)

        EditableFormSet = formset_factory(
            RoundStandardForm,
            formset=RoundStandardFormSet.formset,
            extra=1,
            can_delete=True
        )
        formset = EditableFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            template = form.save()
            existing_ids = set(template.round_standards.values_list('id', flat=True))
            processed_ids = set()

            for i, f in enumerate(formset):
                if not f.cleaned_data:
                    continue
                if f.cleaned_data.get('DELETE'):
                    continue
                round_no = f.cleaned_data.get('round_no')
                rs = template.round_standards.filter(round_no=round_no).first()
                if rs:
                    for field in ['steam_time_min', 'steam_time_max', 'dry_duration_min',
                                  'dry_duration_max', 'weight_loss_max', 'required_color']:
                        setattr(rs, field, f.cleaned_data[field])
                    rs.save()
                    processed_ids.add(rs.id)
                else:
                    rs = f.save(commit=False)
                    rs.template = template
                    rs.save()

            for old_id in existing_ids - processed_ids:
                RoundStandard.objects.filter(id=old_id).delete()

            messages.success(request, f'标准模板「{template.template_name}」更新成功')
            return redirect('herbapp:template_list')

        return render(request, 'herbapp/template_form.html', {
            'form': form,
            'formset': formset,
            'is_edit': True,
            'template': template,
        })


class TemplateDetailView(DetailView):
    model = ProcessingStandardTemplate
    template_name = 'herbapp/template_detail.html'
    context_object_name = 'template'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['round_standards'] = self.object.round_standards.all().order_by('round_no')
        ctx['batch_count'] = self.object.batches.count()
        return ctx


class TemplateDeleteView(DeleteView):
    model = ProcessingStandardTemplate
    template_name = 'herbapp/template_confirm_delete.html'
    success_url = reverse_lazy('herbapp:template_list')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        batch_count = self.object.batches.count()
        if batch_count > 0:
            messages.error(request, f'该模板已被{batch_count}个批次引用，无法删除')
            return redirect('herbapp:template_detail', pk=self.object.pk)
        messages.success(request, f'标准模板「{self.object.template_name}」已删除')
        return super().delete(request, *args, **kwargs)


class TemplateDetailApi(View):
    def get(self, request, pk):
        template = get_object_or_404(ProcessingStandardTemplate, pk=pk)
        round_standards = []
        for rs in template.round_standards.all().order_by('round_no'):
            round_standards.append({
                'round_no': rs.round_no,
                'steam_time_min': float(rs.steam_time_min),
                'steam_time_max': float(rs.steam_time_max),
                'dry_duration_min': float(rs.dry_duration_min),
                'dry_duration_max': float(rs.dry_duration_max),
                'weight_loss_max': float(rs.weight_loss_max),
                'required_color': rs.required_color,
                'required_color_display': rs.get_required_color_display(),
            })
        return JsonResponse({
            'template_name': template.template_name,
            'herb_name': template.herb_name,
            'total_rounds': template.total_rounds,
            'description': template.description or '',
            'round_standards': round_standards,
        })


class BatchListView(ListView):
    model = HerbBatch
    template_name = 'herbapp/batch_list.html'
    context_object_name = 'batches'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        keyword = self.request.GET.get('q', '')
        status = self.request.GET.get('status', '')
        if keyword:
            queryset = queryset.filter(
                Q(batch_no__icontains=keyword) | Q(herb_name__icontains=keyword)
            )
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        ctx['status'] = self.request.GET.get('status', '')
        ctx['status_choices'] = HerbBatch.STATUS_CHOICES
        return ctx


class BatchCreateView(CreateView):
    model = HerbBatch
    form_class = HerbBatchForm
    template_name = 'herbapp/batch_form.html'
    success_url = reverse_lazy('herbapp:batch_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['is_edit'] = False
        return ctx


class BatchDetailView(DetailView):
    model = HerbBatch
    template_name = 'herbapp/batch_detail.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        rounds = self.object.rounds.all().order_by('round_no')
        ctx['rounds'] = rounds
        ctx['next_round_no'] = self.object.get_next_round_no()
        ctx['can_add_round'] = self.object.can_add_round()
        ctx['can_accept'] = self.object.can_accept()
        ctx['has_accepted'] = self.object.status == HerbBatch.STATUS_ACCEPTED
        ctx['quality_assessment'] = getattr(self.object, 'quality_assessment', None)
        ctx['pending_review_count'] = rounds.filter(
            is_abnormal=True,
            review_status=ProcessingRound.REVIEW_PENDING
        ).count()
        return ctx


class RoundCreateView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_add_round():
            return redirect('herbapp:batch_detail', pk=pk)
        form = ProcessingRoundForm(batch=batch)
        round_no = batch.get_next_round_no()

        standard_info = None
        if batch.template_id:
            rs = batch.template.round_standards.filter(round_no=round_no).first()
            if rs:
                standard_info = {
                    'round_no': rs.round_no,
                    'steam_time_min': float(rs.steam_time_min),
                    'steam_time_max': float(rs.steam_time_max),
                    'dry_duration_min': float(rs.dry_duration_min),
                    'dry_duration_max': float(rs.dry_duration_max),
                    'weight_loss_max': float(rs.weight_loss_max),
                    'required_color': rs.required_color,
                    'required_color_display': rs.get_required_color_display(),
                }

        ctx = {
            'form': form,
            'batch': batch,
            'round_no': round_no,
            'standard_info': standard_info,
            'previous_weight': float(batch.initial_weight),
        }
        prev_round = rounds = batch.rounds.order_by('-round_no').first()
        if prev_round:
            ctx['previous_weight'] = float(prev_round.weight)
        return render(request, 'herbapp/round_form.html', ctx)

    def post(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_add_round():
            return redirect('herbapp:batch_detail', pk=pk)

        form = ProcessingRoundForm(request.POST, batch=batch)
        if form.is_valid():
            round_obj = form.save(commit=False)
            round_obj.batch = batch
            round_obj.round_no = batch.get_next_round_no()
            round_obj.detect_abnormalities()
            round_obj.save()
            batch.update_status()
            if round_obj.is_abnormal:
                messages.warning(request, f'第{round_obj.round_no}轮数据检测到异常，请确保处理意见已填写完整')
            return redirect('herbapp:batch_detail', pk=pk)

        round_no = batch.get_next_round_no()
        standard_info = None
        if batch.template_id:
            rs = batch.template.round_standards.filter(round_no=round_no).first()
            if rs:
                standard_info = {
                    'round_no': rs.round_no,
                    'steam_time_min': float(rs.steam_time_min),
                    'steam_time_max': float(rs.steam_time_max),
                    'dry_duration_min': float(rs.dry_duration_min),
                    'dry_duration_max': float(rs.dry_duration_max),
                    'weight_loss_max': float(rs.weight_loss_max),
                    'required_color': rs.required_color,
                    'required_color_display': rs.get_required_color_display(),
                }
        ctx = {
            'form': form,
            'batch': batch,
            'round_no': round_no,
            'standard_info': standard_info,
            'previous_weight': float(batch.initial_weight),
        }
        prev_round = batch.rounds.order_by('-round_no').first()
        if prev_round:
            ctx['previous_weight'] = float(prev_round.weight)
        return render(request, 'herbapp/round_form.html', ctx)


class RoundCheckAbnormalApi(View):
    def post(self, request, batch_pk, round_no):
        batch = get_object_or_404(HerbBatch, pk=batch_pk)
        try:
            steam_time = float(request.POST.get('steam_time', 0))
            dry_duration = float(request.POST.get('dry_duration', 0))
            weight = float(request.POST.get('weight', 0))
            color_rating = request.POST.get('color_rating', '')
        except (ValueError, TypeError):
            return JsonResponse({'ok': False, 'error': '参数无效'})

        temp_round = ProcessingRound(
            batch=batch,
            round_no=round_no,
            steam_time=steam_time,
            dry_duration=dry_duration,
            weight=weight,
            color_rating=color_rating,
        )
        is_abnormal, reasons = temp_round.detect_abnormalities()

        return JsonResponse({
            'ok': True,
            'is_abnormal': is_abnormal,
            'reasons': reasons,
            'weight_loss_percent': temp_round.get_weight_loss_percent(),
        })


class RoundReviewView(View):
    def get(self, request, batch_pk, round_no):
        batch = get_object_or_404(HerbBatch, pk=batch_pk)
        round_obj = get_object_or_404(ProcessingRound, batch=batch, round_no=round_no)
        if not round_obj.is_abnormal:
            messages.info(request, '该轮次无异常，无需复核')
            return redirect('herbapp:batch_detail', pk=batch_pk)
        form = RoundReviewForm(instance=round_obj)
        return render(request, 'herbapp/review_form.html', {
            'form': form,
            'batch': batch,
            'round': round_obj,
        })

    def post(self, request, batch_pk, round_no):
        batch = get_object_or_404(HerbBatch, pk=batch_pk)
        round_obj = get_object_or_404(ProcessingRound, batch=batch, round_no=round_no)
        form = RoundReviewForm(request.POST, instance=round_obj)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.reviewed_at = timezone.now()
            obj.save()
            messages.success(request, f'第{round_no}轮复核完成')
            return redirect('herbapp:batch_detail', pk=batch_pk)
        return render(request, 'herbapp/review_form.html', {
            'form': form,
            'batch': batch,
            'round': round_obj,
        })


class AcceptanceView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_accept():
            return redirect('herbapp:batch_detail', pk=pk)
        form = AcceptanceForm()
        return render(request, 'herbapp/acceptance_form.html', {
            'form': form,
            'batch': batch,
        })

    def post(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        if not batch.can_accept():
            return redirect('herbapp:batch_detail', pk=pk)

        form = AcceptanceForm(request.POST)
        if form.is_valid():
            acceptance = form.save(commit=False)
            acceptance.batch = batch
            acceptance.save()
            batch.status = HerbBatch.STATUS_ACCEPTED
            batch.save()
            BatchQualityAssessment.generate_assessment(
                batch,
                evaluator=request.user.username if request.user.is_authenticated else '',
            )
            messages.success(request, f'批次{batch.batch_no}验收完成，已生成质量总评')
            return redirect('herbapp:batch_detail', pk=pk)

        return render(request, 'herbapp/acceptance_form.html', {
            'form': form,
            'batch': batch,
        })


class BatchGenerateAssessmentView(View):
    def post(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        form = QualityAssessmentForm(request.POST)
        if form.is_valid():
            assessment = BatchQualityAssessment.generate_assessment(
                batch,
                evaluator=form.cleaned_data.get('evaluator', ''),
                remark=form.cleaned_data.get('evaluation_remark', ''),
            )
            if assessment:
                messages.success(request, f'质量总评已生成，综合评分{assessment.final_score}分')
            else:
                messages.warning(request, '暂无轮次数据，无法生成质量总评')
        return redirect('herbapp:batch_detail', pk=pk)


class BatchChartView(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        rounds = batch.rounds.all().order_by('round_no')

        labels = ['初始']
        weight_data = [float(batch.initial_weight)]
        color_map = {
            ProcessingRound.COLOR_EXCELLENT: 4,
            ProcessingRound.COLOR_GOOD: 3,
            ProcessingRound.COLOR_NORMAL: 2,
            ProcessingRound.COLOR_ABNORMAL: 1,
        }
        color_data = []
        abnormal_flags = []
        steam_times = []
        dry_durations = []
        weight_losses = []

        for r in rounds:
            labels.append(f'第{r.round_no}轮')
            weight_data.append(float(r.weight))
            color_data.append({
                'round': r.round_no,
                'rating': r.get_color_rating_display(),
                'value': color_map.get(r.color_rating, 0),
                'abnormal': r.is_abnormal,
            })
            abnormal_flags.append({
                'round': r.round_no,
                'is_abnormal': r.is_abnormal,
                'reasons': list(r.abnormal_reasons.values()) if isinstance(r.abnormal_reasons, dict) else [],
            })
            steam_times.append(float(r.steam_time))
            dry_durations.append(float(r.dry_duration))
            weight_losses.append(r.get_weight_loss_percent())

        standard_data = None
        if batch.template_id:
            std_rounds = batch.template.round_standards.all()
            if std_rounds.exists():
                standard_data = {
                    'steam': [(float(s.steam_time_min) + float(s.steam_time_max)) / 2 for s in std_rounds.order_by('round_no')],
                    'dry': [(float(s.dry_duration_min) + float(s.dry_duration_max)) / 2 for s in std_rounds.order_by('round_no')],
                    'weight_loss_max': [float(s.weight_loss_max) for s in std_rounds.order_by('round_no')],
                }

        result = {
            'labels': labels,
            'weight_data': weight_data,
            'color_data': color_data,
            'initial_weight': float(batch.initial_weight),
            'required_rounds': batch.required_rounds,
            'abnormal_flags': abnormal_flags,
            'steam_times': steam_times,
            'dry_durations': dry_durations,
            'weight_losses': weight_losses,
            'standard_data': standard_data,
        }

        assessment = getattr(batch, 'quality_assessment', None)
        if assessment:
            result['assessment'] = {
                'final_score': float(assessment.final_score),
                'overall_grade': assessment.get_overall_grade_display(),
                'total_weight_loss': float(assessment.total_weight_loss_percent),
                'avg_color_score': float(assessment.avg_color_score),
                'abnormal_count': assessment.abnormal_count,
                'steam_deviation': float(assessment.steam_time_deviation),
                'dry_deviation': float(assessment.dry_duration_deviation),
            }

        return JsonResponse(result)


class BatchCompareView(View):
    def get(self, request):
        form = BatchCompareForm()
        return render(request, 'herbapp/batch_compare.html', {
            'form': form,
            'results': None,
        })

    def post(self, request):
        form = BatchCompareForm(request.POST)
        results = None
        if form.is_valid():
            batches = form.cleaned_data['batches']
            results = self._build_compare_data(batches)
        return render(request, 'herbapp/batch_compare.html', {
            'form': form,
            'results': results,
        })

    def _build_compare_data(self, batches):
        batch_ids = [b.pk for b in batches]
        assessments = BatchQualityAssessment.objects.filter(batch_id__in=batch_ids)
        assess_map = {a.batch_id: a for a in assessments}

        items = []
        weight_series = []
        loss_series = []
        color_series = []
        abnormal_series = []
        all_labels = set()

        for batch in batches:
            rounds = batch.rounds.all().order_by('round_no')
            round_labels = [f'第{r.round_no}轮' for r in rounds]
            all_labels.update(round_labels)

            weight_data = [float(batch.initial_weight)] + [float(r.weight) for r in rounds]
            loss_data = [0] + [r.get_weight_loss_percent() for r in rounds]
            color_map_vals = {'excellent': 4, 'good': 3, 'normal': 2, 'abnormal': 1}
            color_data = [color_map_vals.get(r.color_rating, 0) for r in rounds]
            abnormal_count = rounds.filter(is_abnormal=True).count()

            assess = assess_map.get(batch.pk)

            items.append({
                'batch': batch,
                'rounds_count': rounds.count(),
                'weight_data': weight_data,
                'loss_data': loss_data,
                'color_data': color_data,
                'abnormal_count': abnormal_count,
                'assessment': assess,
                'final_weight': float(rounds.last().weight) if rounds.exists() else float(batch.initial_weight),
                'total_loss': rounds.last().get_weight_loss_percent() if rounds.exists() else 0,
            })

        labels = sorted(all_labels, key=lambda x: int(x.replace('第', '').replace('轮', '')))

        chart_data = {
            'labels': ['初始'] + labels,
            'batches': [],
            'loss_labels': ['初始'] + labels,
        }
        for i, item in enumerate(items):
            chart_data['batches'].append({
                'name': item['batch'].batch_no,
                'weight': item['weight_data'],
                'loss': item['loss_data'],
                'color': ['#8B4513', '#2E8B57', '#B8860B', '#4682B4', '#8A2BE2'][i % 5],
                'score': float(item['assessment'].final_score) if item['assessment'] else None,
                'grade': item['assessment'].get_overall_grade_display() if item['assessment'] else '未评估',
                'abnormal_count': item['abnormal_count'],
            })

        return {
            'items': items,
            'chart_data': chart_data,
            'summary': self._build_summary(items),
        }

    def _build_summary(self, items):
        scored = [i for i in items if i['assessment']]
        if not scored:
            return None

        best = max(scored, key=lambda x: float(x['assessment'].final_score))
        worst = min(scored, key=lambda x: float(x['assessment'].final_score))
        avg_score = round(sum(float(i['assessment'].final_score) for i in scored) / len(scored), 2)
        avg_loss = round(sum(i['total_loss'] for i in items) / len(items), 2)
        total_abnormal = sum(i['abnormal_count'] for i in items)

        return {
            'best': best['batch'].batch_no,
            'best_score': float(best['assessment'].final_score),
            'worst': worst['batch'].batch_no,
            'worst_score': float(worst['assessment'].final_score),
            'avg_score': avg_score,
            'avg_loss': avg_loss,
            'total_abnormal': total_abnormal,
            'count': len(items),
        }


class BatchCompareApi(View):
    def get(self, request):
        ids_str = request.GET.get('ids', '')
        try:
            ids = [int(x) for x in ids_str.split(',') if x.strip()]
        except ValueError:
            return JsonResponse({'ok': False, 'error': '无效的批次ID'})
        if len(ids) < 2:
            return JsonResponse({'ok': False, 'error': '至少需要2个批次'})

        batches = HerbBatch.objects.filter(pk__in=ids)
        if batches.count() < 2:
            return JsonResponse({'ok': False, 'error': '有效批次不足2个'})

        view = BatchCompareView()
        results = view._build_compare_data(batches)

        return JsonResponse({
            'ok': True,
            'chart_data': results['chart_data'],
            'summary': results['summary'],
        })
