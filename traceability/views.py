from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, ListView, DetailView
from django.http import JsonResponse
from django.db.models import Q, Count, Avg, Min, Max
from django.utils import timezone
from collections import defaultdict
import statistics

from herbapp.models import (
    HerbBatch, ProcessingRound, Acceptance, BatchQualityAssessment,
    ProcessingStandardTemplate
)
from processing.models import (
    EnvironmentRecord, EquipmentStatusRecord, Equipment,
    DryingAreaRecord, InspectionRecord, EnvironmentStandard
)


class TraceabilityDashboardView(TemplateView):
    template_name = 'traceability/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        batches = HerbBatch.objects.all()
        total_batches = batches.count()
        processing_batches = batches.filter(status='processing').count()
        completed_batches = batches.filter(status__in=['completed', 'accepted']).count()

        all_abnormal_count = (
            ProcessingRound.objects.filter(is_abnormal=True).count()
            + EnvironmentRecord.objects.filter(is_abnormal=True).count()
            + EquipmentStatusRecord.objects.filter(is_abnormal=True).count()
            + DryingAreaRecord.objects.filter(is_abnormal=True).count()
            + InspectionRecord.objects.filter(inspection_result='abnormal').count()
        )

        untreated_count = self._count_untreated_warnings()
        critical_alerts = self._detect_critical_alerts()

        ctx.update({
            'total_batches': total_batches,
            'processing_batches': processing_batches,
            'completed_batches': completed_batches,
            'all_abnormal_count': all_abnormal_count,
            'untreated_count': untreated_count,
            'critical_count': len(critical_alerts),
            'recent_batches': batches.order_by('-created_at')[:8],
            'critical_alerts': critical_alerts[:10],
            'warning_summary': self._warning_summary(),
            'quality_overview': self._quality_overview(),
        })
        return ctx

    def _count_untreated_warnings(self):
        count = 0
        count += ProcessingRound.objects.filter(
            is_abnormal=True, review_status='pending'
        ).count()
        count += EnvironmentRecord.objects.filter(
            is_abnormal=True, handling_opinion=''
        ).count()
        count += EquipmentStatusRecord.objects.filter(
            is_abnormal=True, handling_result=''
        ).count()
        count += DryingAreaRecord.objects.filter(
            is_abnormal=True, handling_opinion=''
        ).count()
        count += InspectionRecord.objects.filter(
            Q(inspection_result='abnormal', handling_result='') |
            Q(inspection_result='pending')
        ).count()
        count += Equipment.objects.filter(status='fault').count()
        return count

    def _detect_critical_alerts(self):
        alerts = []

        for batch in HerbBatch.objects.filter(status__in=['pending', 'processing']):
            env_records = list(batch.env_records.order_by('-record_time')[:3])
            if len(env_records) >= 2:
                last_two_abnormal = all(r.is_abnormal for r in env_records[:2])
                if last_two_abnormal:
                    alerts.append({
                        'level': 'critical',
                        'type': '连续超标',
                        'batch': batch,
                        'description': f'批次{batch.batch_no}连续2次环境监测参数超标，请关注！',
                        'time': env_records[0].record_time,
                        'url': reverse('traceability:batch_trace', kwargs={'pk': batch.pk}),
                    })

            drying_records = list(batch.drying_records.order_by('-record_time')[:3])
            if len(drying_records) >= 2:
                last_two_abnormal = all(r.is_abnormal for r in drying_records[:2])
                if last_two_abnormal:
                    alerts.append({
                        'level': 'high',
                        'type': '连续超标',
                        'batch': batch,
                        'description': f'批次{batch.batch_no}晾晒区条件连续异常，请检查！',
                        'time': drying_records[0].record_time,
                        'url': reverse('traceability:batch_trace', kwargs={'pk': batch.pk}),
                    })

            rounds = list(batch.rounds.order_by('-round_no')[:3])
            if len(rounds) >= 2:
                last_two_abnormal = all(r.is_abnormal for r in rounds[:2])
                if last_two_abnormal:
                    alerts.append({
                        'level': 'high',
                        'type': '连续超标',
                        'batch': batch,
                        'description': f'批次{batch.batch_no}炮制参数连续两轮异常！',
                        'time': rounds[0].record_time,
                        'url': reverse('traceability:batch_trace', kwargs={'pk': batch.pk}),
                    })

        for equip in Equipment.objects.filter(status='fault'):
            fault_records = equip.status_records.filter(
                is_abnormal=True, handling_result=''
            ).order_by('-record_time')
            if fault_records.exists():
                fr = fault_records.first()
                alerts.append({
                    'level': 'critical',
                    'type': '设备故障',
                    'batch': fr.batch if fr.batch_id else None,
                    'equipment': equip,
                    'description': f'设备{equip.equipment_no}({equip.equipment_name})故障未关闭，处理结果未填写！',
                    'time': fr.record_time,
                    'url': reverse('processing:equipment_detail', kwargs={'pk': equip.pk}),
                })

        for r in ProcessingRound.objects.filter(
            is_abnormal=True, review_status='pending'
        ).order_by('-record_time'):
            alerts.append({
                'level': 'warning',
                'type': '未处理异常',
                'batch': r.batch,
                'description': f'第{r.round_no}轮数据异常，复核状态为待处理',
                'time': r.record_time,
                'url': reverse('herbapp:round_review', kwargs={'batch_pk': r.batch_id, 'round_no': r.round_no}),
            })

        for e in EnvironmentRecord.objects.filter(
            is_abnormal=True, handling_opinion=''
        ).order_by('-record_time'):
            if isinstance(e.abnormal_details, dict):
                env_msg = '; '.join(e.abnormal_details.values())
            else:
                env_msg = str(e.abnormal_details)
            alerts.append({
                'level': 'warning',
                'type': '未处理异常',
                'batch': e.batch,
                'description': f'环境监测异常：{env_msg}',
                'time': e.record_time,
                'url': reverse('processing:env_record_detail', kwargs={'pk': e.pk}),
            })

        for i in InspectionRecord.objects.filter(
            Q(inspection_result='abnormal', handling_result='') |
            Q(inspection_result='pending')
        ).order_by('-inspection_time'):
            desc = '巡检结果待确认' if i.inspection_result == 'pending' else f'巡检异常：{i.abnormal_description or ""}'
            alerts.append({
                'level': 'warning',
                'type': '巡检未闭环',
                'batch': i.batch,
                'equipment': i.equipment,
                'description': desc,
                'time': i.inspection_time,
                'url': reverse('processing:inspection_detail', kwargs={'pk': i.pk}),
            })

        alerts.sort(key=lambda x: x.get('time', timezone.now()), reverse=True)
        return alerts

    def _warning_summary(self):
        return {
            'round_pending': ProcessingRound.objects.filter(is_abnormal=True, review_status='pending').count(),
            'env_untreated': EnvironmentRecord.objects.filter(is_abnormal=True, handling_opinion='').count(),
            'equip_untreated': EquipmentStatusRecord.objects.filter(is_abnormal=True, handling_result='').count(),
            'drying_untreated': DryingAreaRecord.objects.filter(is_abnormal=True, handling_opinion='').count(),
            'inspection_issue': InspectionRecord.objects.filter(
                Q(inspection_result='abnormal', handling_result='') |
                Q(inspection_result='pending')
            ).count(),
            'equip_fault': Equipment.objects.filter(status='fault').count(),
        }

    def _quality_overview(self):
        assessments = BatchQualityAssessment.objects.all()
        if not assessments.exists():
            return None
        scores = [float(a.final_score) for a in assessments]
        grade_count = assessments.values('overall_grade').annotate(
            cnt=Count('id')
        )
        grade_map = {g['overall_grade']: g['cnt'] for g in grade_count}
        return {
            'avg_score': round(sum(scores) / len(scores), 2),
            'max_score': round(max(scores), 2),
            'min_score': round(min(scores), 2),
            'total_assessed': assessments.count(),
            'excellent': grade_map.get('excellent', 0),
            'good': grade_map.get('good', 0),
            'normal': grade_map.get('normal', 0),
            'poor': grade_map.get('poor', 0),
        }


class BatchTraceabilityView(DetailView):
    model = HerbBatch
    template_name = 'traceability/batch_traceability.html'
    context_object_name = 'batch'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        batch = self.object

        rounds = batch.rounds.all().order_by('round_no')
        env_records = batch.env_records.all().order_by('record_time')
        equipment_records = batch.equipment_records.all().order_by('record_time')
        drying_records = batch.drying_records.all().order_by('record_time')
        inspection_records = batch.inspection_records.all().order_by('inspection_time')

        abnormal_rounds = rounds.filter(is_abnormal=True)
        abnormal_env = env_records.filter(is_abnormal=True)
        abnormal_equip = equipment_records.filter(is_abnormal=True)
        abnormal_drying = drying_records.filter(is_abnormal=True)
        abnormal_inspection = inspection_records.filter(
            Q(inspection_result='abnormal') | Q(inspection_result='pending')
        )

        pending_rounds = abnormal_rounds.filter(review_status='pending')
        pending_env = abnormal_env.filter(handling_opinion='')
        pending_equip = abnormal_equip.filter(handling_result='')
        pending_drying = abnormal_drying.filter(handling_opinion='')
        pending_inspection = abnormal_inspection.filter(
            Q(inspection_result='pending') | Q(handling_result='')
        )

        ctx.update({
            'rounds': rounds,
            'env_records': env_records,
            'equipment_records': equipment_records,
            'drying_records': drying_records,
            'inspection_records': inspection_records,

            'abnormal_rounds': abnormal_rounds,
            'abnormal_env': abnormal_env,
            'abnormal_equip': abnormal_equip,
            'abnormal_drying': abnormal_drying,
            'abnormal_inspection': abnormal_inspection,

            'pending_rounds': pending_rounds,
            'pending_env': pending_env,
            'pending_equip': pending_equip,
            'pending_drying': pending_drying,
            'pending_inspection': pending_inspection,

            'total_abnormal': (
                abnormal_rounds.count() + abnormal_env.count() +
                abnormal_equip.count() + abnormal_drying.count() +
                abnormal_inspection.count()
            ),
            'total_pending': (
                pending_rounds.count() + pending_env.count() +
                pending_equip.count() + pending_drying.count() +
                pending_inspection.count()
            ),

            'quality_assessment': getattr(batch, 'quality_assessment', None),
            'acceptance': getattr(batch, 'acceptance', None),
        })
        return ctx


class BatchTimelineApi(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)
        timeline = []

        timeline.append({
            'id': f'create-{batch.pk}',
            'type': 'batch_create',
            'type_display': '批次创建',
            'time': batch.created_at,
            'icon': '📦',
            'color': '#8B4513',
            'content': f'创建批次「{batch.batch_no}」，药材：{batch.herb_name}，初始重量：{batch.initial_weight}g，规定轮次：{batch.required_rounds}轮',
            'status': 'completed',
            'url': reverse('herbapp:batch_detail', kwargs={'pk': batch.pk}),
        })

        for r in batch.rounds.all().order_by('round_no'):
            abnormal_note = ''
            if r.is_abnormal:
                reasons = list(r.abnormal_reasons.values()) if isinstance(r.abnormal_reasons, dict) else []
                abnormal_note = ' ⚠️ ' + '；'.join(reasons) if reasons else ' ⚠️ 异常'
            review_note = ''
            if r.is_abnormal:
                if r.review_status == 'pending':
                    review_note = ' [待复核]'
                elif r.review_status == 'pass':
                    review_note = f' [✓复核通过：{r.reviewer or ""}]'
                else:
                    review_note = f' [✗复核驳回：{r.reviewer or ""}]'
            timeline.append({
                'id': f'round-{r.pk}',
                'type': 'round',
                'type_display': f'第{r.round_no}轮炮制',
                'round_no': r.round_no,
                'time': r.record_time,
                'icon': '🔥',
                'color': '#D2691E' if not r.is_abnormal else '#B22222',
                'content': (
                    f'蒸制{r.steam_time}分钟，晾晒{r.dry_duration}小时，'
                    f'重量{r.weight}g（损耗{r.get_weight_loss_percent()}%），'
                    f'色泽{r.get_color_rating_display()}'
                    f'{abnormal_note}{review_note}'
                ),
                'status': 'abnormal' if r.is_abnormal and r.review_status == 'pending' else ('handled' if r.is_abnormal else 'completed'),
                'is_abnormal': r.is_abnormal,
                'review_status': r.review_status if r.is_abnormal else None,
                'url': reverse('herbapp:round_review', kwargs={'batch_pk': batch.pk, 'round_no': r.round_no}) if r.is_abnormal else None,
            })

        for e in batch.env_records.all().order_by('record_time'):
            abnormal_note = ''
            pending_note = ''
            if e.is_abnormal:
                details = list(e.abnormal_details.values()) if isinstance(e.abnormal_details, dict) else []
                abnormal_note = ' ⚠️ ' + '；'.join(details) if details else ' ⚠️ 异常'
                if not e.handling_opinion:
                    pending_note = ' [未处理]'
                else:
                    pending_note = f' [处理：{e.handling_opinion[:30]}]'
            timeline.append({
                'id': f'env-{e.pk}',
                'type': 'env',
                'type_display': '环境监测',
                'round_no': e.round_no,
                'time': e.record_time,
                'icon': '🌡️',
                'color': '#4682B4' if not e.is_abnormal else '#B22222',
                'content': (
                    f'{f"第{e.round_no}轮" if e.round_no else "过程"}监测'
                    f'{f"｜位置：{e.location}" if e.location else ""}'
                    f'｜温度{e.temperature}°C' if e.temperature else ''
                    f'{f"｜湿度{e.humidity}%RH" if e.humidity else ""}'
                    f'{abnormal_note}{pending_note}'
                ),
                'status': 'abnormal' if e.is_abnormal and not e.handling_opinion else ('handled' if e.is_abnormal else 'completed'),
                'is_abnormal': e.is_abnormal,
                'url': reverse('processing:env_record_detail', kwargs={'pk': e.pk}),
            })

        for eq in batch.equipment_records.all().order_by('record_time'):
            abnormal_note = ''
            pending_note = ''
            if eq.is_abnormal:
                abnormal_note = f' ⚠️ {eq.abnormal_description or "设备异常"}'
                if not eq.handling_result:
                    pending_note = ' [未处理]'
                else:
                    pending_note = f' [处理：{eq.handling_result[:30]}]'
            timeline.append({
                'id': f'equip-{eq.pk}',
                'type': 'equipment',
                'type_display': '设备使用',
                'round_no': eq.round_no,
                'time': eq.record_time,
                'icon': '⚙️',
                'color': '#696969' if not eq.is_abnormal else '#B22222',
                'content': (
                    f'{f"第{eq.round_no}轮" if eq.round_no else "过程"}使用 '
                    f'{eq.equipment.equipment_no}({eq.equipment.equipment_name}) '
                    f'状态{eq.get_running_status_display()}'
                    f'{abnormal_note}{pending_note}'
                ),
                'status': 'abnormal' if eq.is_abnormal and not eq.handling_result else ('handled' if eq.is_abnormal else 'completed'),
                'is_abnormal': eq.is_abnormal,
                'url': reverse('processing:equipment_status_detail', kwargs={'pk': eq.pk}),
            })

        for d in batch.drying_records.all().order_by('record_time'):
            abnormal_note = ''
            pending_note = ''
            if d.is_abnormal:
                details = list(d.abnormal_details.values()) if isinstance(d.abnormal_details, dict) else []
                abnormal_note = ' ⚠️ ' + '；'.join(details) if details else ' ⚠️ 异常'
                if not d.handling_opinion:
                    pending_note = ' [未处理]'
                else:
                    pending_note = f' [处理：{d.handling_opinion[:30]}]'
            timeline.append({
                'id': f'drying-{d.pk}',
                'type': 'drying',
                'type_display': '晾晒记录',
                'round_no': d.round_no,
                'time': d.record_time,
                'icon': '☀️',
                'color': '#DAA520' if not d.is_abnormal else '#B22222',
                'content': (
                    f'{f"第{d.round_no}轮" if d.round_no else "过程"}'
                    f'区域：{d.area_name}({d.get_area_type_display()})'
                    f'{f"｜温度{d.temperature}°C" if d.temperature else ""}'
                    f'{f"｜湿度{d.humidity}%RH" if d.humidity else ""}'
                    f'{f"｜光照{d.light_intensity}Lux" if d.light_intensity else ""}'
                    f'{abnormal_note}{pending_note}'
                ),
                'status': 'abnormal' if d.is_abnormal and not d.handling_opinion else ('handled' if d.is_abnormal else 'completed'),
                'is_abnormal': d.is_abnormal,
                'url': reverse('processing:drying_record_detail', kwargs={'pk': d.pk}),
            })

        for i in batch.inspection_records.all().order_by('inspection_time'):
            abnormal_note = ''
            pending_note = ''
            if i.inspection_result == 'abnormal':
                abnormal_note = f' ⚠️ {i.abnormal_description or "巡检异常"}'
                if not i.handling_result:
                    pending_note = ' [未处理]'
                else:
                    pending_note = f' [处理：{i.handling_result[:30]}]'
            elif i.inspection_result == 'pending':
                pending_note = ' [待确认]'
            equip_note = f'｜设备：{i.equipment.equipment_name}' if i.equipment_id else ''
            timeline.append({
                'id': f'inspect-{i.pk}',
                'type': 'inspection',
                'type_display': '巡检记录',
                'round_no': None,
                'time': i.inspection_time,
                'icon': '🔍',
                'color': '#2E8B57' if i.inspection_result == 'normal' else ('#B8860B' if i.inspection_result == 'pending' else '#B22222'),
                'content': (
                    f'{i.get_inspection_type_display()}｜'
                    f'巡检人{i.inspector}'
                    f'{equip_note}'
                    f'｜结果{i.get_inspection_result_display()}'
                    f'{abnormal_note}{pending_note}'
                ),
                'status': 'abnormal' if (i.inspection_result == 'abnormal' and not i.handling_result) or i.inspection_result == 'pending' else ('handled' if i.inspection_result == 'abnormal' else 'completed'),
                'is_abnormal': i.inspection_result != 'normal',
                'url': reverse('processing:inspection_detail', kwargs={'pk': i.pk}),
            })

        if hasattr(batch, 'acceptance'):
            a = batch.acceptance
            timeline.append({
                'id': f'accept-{a.pk}',
                'type': 'acceptance',
                'type_display': '验收',
                'time': a.accepted_at,
                'icon': '✅' if a.result != 'fail' else '❌',
                'color': '#2E8B57' if a.result != 'fail' else '#B22222',
                'content': f'批次验收，结果：{a.get_result_display()}{f"｜备注：{a.remark[:40]}" if a.remark else ""}',
                'status': 'completed',
                'url': reverse('herbapp:batch_detail', kwargs={'pk': batch.pk}),
            })

        if hasattr(batch, 'quality_assessment'):
            qa = batch.quality_assessment
            grade_color = {
                'excellent': '#2E8B57', 'good': '#4682B4',
                'normal': '#B8860B', 'poor': '#B22222',
            }
            timeline.append({
                'id': f'qa-{qa.pk}',
                'type': 'assessment',
                'type_display': '质量总评',
                'time': qa.created_at,
                'icon': '🏆',
                'color': grade_color.get(qa.overall_grade, '#666'),
                'content': (
                    f'综合评分{qa.final_score}/100，评级{qa.get_overall_grade_display()}'
                    f'｜重量损耗{qa.total_weight_loss_percent}%'
                    f'｜色泽均分{qa.avg_color_score}'
                    f'｜异常{qa.abnormal_count}次'
                    f'{f"｜评估人{qa.evaluator}" if qa.evaluator else ""}'
                ),
                'status': 'completed',
                'url': reverse('herbapp:batch_detail', kwargs={'pk': batch.pk}),
            })

        timeline.sort(key=lambda x: x['time'])
        for idx, item in enumerate(timeline):
            item['order'] = idx + 1

        return JsonResponse({
            'ok': True,
            'batch': {
                'batch_no': batch.batch_no,
                'herb_name': batch.herb_name,
                'status': batch.get_status_display(),
                'created_at': batch.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            },
            'timeline': timeline,
        })


class BatchQualityTrendApi(View):
    def get(self, request, pk):
        batch = get_object_or_404(HerbBatch, pk=pk)

        rounds = batch.rounds.all().order_by('round_no')
        labels = [f'第{r.round_no}轮' for r in rounds]

        weight_loss = [r.get_weight_loss_percent() for r in rounds]

        color_map = {'excellent': 100, 'good': 85, 'normal': 70, 'abnormal': 40}
        color_scores = [color_map.get(r.color_rating, 0) for r in rounds]

        steam_times = [float(r.steam_time) for r in rounds]
        dry_durations = [float(r.dry_duration) for r in rounds]

        abnormal_flags = []
        for idx, r in enumerate(rounds):
            if r.is_abnormal:
                abnormal_flags.append({
                    'index': idx,
                    'round': r.round_no,
                    'reasons': list(r.abnormal_reasons.values()) if isinstance(r.abnormal_reasons, dict) else [],
                    'review': r.get_review_status_display() if r.is_abnormal else None,
                })

        env_records = batch.env_records.all().order_by('record_time')
        env_labels = [er.record_time.strftime('%m-%d %H:%M') for er in env_records]
        env_temps = [float(er.temperature) if er.temperature else None for er in env_records]
        env_hums = [float(er.humidity) if er.humidity else None for er in env_records]

        env_abnormal_flags = []
        for idx, er in enumerate(env_records):
            if er.is_abnormal:
                env_abnormal_flags.append({
                    'index': idx,
                    'details': list(er.abnormal_details.values()) if isinstance(er.abnormal_details, dict) else [],
                    'handling': er.handling_opinion or '未处理',
                })

        drying_records = batch.drying_records.all().order_by('record_time')
        drying_labels = [dr.record_time.strftime('%m-%d %H:%M') for dr in drying_records]
        drying_temps = [float(dr.temperature) if dr.temperature else None for dr in drying_records]
        drying_hums = [float(dr.humidity) if dr.humidity else None for dr in drying_records]

        standards = EnvironmentStandard.objects.filter(
            herb_name=batch.herb_name, is_active=True
        )
        standard_bounds = {}
        for s in standards:
            key = f'{s.param_type}_{s.stage}'
            standard_bounds[key] = {
                'min': float(s.min_value),
                'max': float(s.max_value),
                'display': s.get_param_type_display(),
            }

        equip_stats = list(
            batch.equipment_records.values(
                'equipment__equipment_no', 'equipment__equipment_name'
            ).annotate(
                total=Count('id'),
                abnormal=Count('id', filter=Q(is_abnormal=True)),
            ).order_by('-abnormal', '-total')
        )

        inspection_stats = {
            'total': batch.inspection_records.count(),
            'normal': batch.inspection_records.filter(inspection_result='normal').count(),
            'abnormal': batch.inspection_records.filter(inspection_result='abnormal').count(),
            'pending': batch.inspection_records.filter(inspection_result='pending').count(),
        }

        assessment = getattr(batch, 'quality_assessment', None)
        assessment_data = None
        if assessment:
            assessment_data = {
                'final_score': float(assessment.final_score),
                'grade': assessment.get_overall_grade_display(),
                'grade_en': assessment.overall_grade,
                'total_loss': float(assessment.total_weight_loss_percent),
                'avg_color': float(assessment.avg_color_score),
                'abnormal_count': assessment.abnormal_count,
                'steam_dev': float(assessment.steam_time_deviation),
                'dry_dev': float(assessment.dry_duration_deviation),
            }

        return JsonResponse({
            'ok': True,
            'round_labels': labels,
            'weight_loss': weight_loss,
            'color_scores': color_scores,
            'steam_times': steam_times,
            'dry_durations': dry_durations,
            'abnormal_flags': abnormal_flags,
            'env_labels': env_labels,
            'env_temps': env_temps,
            'env_hums': env_hums,
            'env_abnormal_flags': env_abnormal_flags,
            'drying_labels': drying_labels,
            'drying_temps': drying_temps,
            'drying_hums': drying_hums,
            'standard_bounds': standard_bounds,
            'equip_stats': equip_stats,
            'inspection_stats': inspection_stats,
            'assessment': assessment_data,
        })


class TraceabilityWarningCenterView(TemplateView):
    template_name = 'traceability/warning_center.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        critical_alerts = self._collect_warnings()
        total_count = len(critical_alerts)
        pending_count = sum(1 for w in critical_alerts if w['status'] == 'pending')
        handled_count = total_count - pending_count

        level_counts = defaultdict(int)
        type_counts = defaultdict(int)
        for w in critical_alerts:
            level_counts[w['level']] += 1
            type_counts[w['type']] += 1

        ctx.update({
            'warnings': critical_alerts[:100],
            'total_count': total_count,
            'pending_count': pending_count,
            'handled_count': handled_count,
            'critical_count': level_counts.get('critical', 0),
            'high_count': level_counts.get('high', 0),
            'warning_count': level_counts.get('warning', 0),
            'type_breakdown': dict(type_counts),
            'filter_type': self.request.GET.get('type', ''),
            'filter_level': self.request.GET.get('level', ''),
            'filter_status': self.request.GET.get('status', ''),
            'batches': HerbBatch.objects.all(),
        })
        return ctx

    def _collect_warnings(self):
        warnings = []
        now = timezone.now()

        for r in ProcessingRound.objects.filter(is_abnormal=True).select_related('batch').order_by('-record_time'):
            status = 'pending' if r.review_status == 'pending' else 'handled'
            if r.review_status == 'pending':
                level = 'critical' if (now - r.record_time).days >= 1 else 'high'
            else:
                level = 'warning'
            reasons = list(r.abnormal_reasons.values()) if isinstance(r.abnormal_reasons, dict) else []
            warnings.append({
                'id': f'round-{r.pk}',
                'level': level,
                'type': '炮制异常',
                'type_en': 'round',
                'batch': r.batch,
                'title': f'第{r.round_no}轮炮制参数异常',
                'description': '；'.join(reasons) if reasons else '检测到数据异常',
                'time': r.record_time,
                'status': status,
                'status_display': '待复核' if status == 'pending' else r.get_review_status_display(),
                'handling': r.review_result if r.review_status != 'pending' else '',
                'handler': r.reviewer if r.review_status != 'pending' else '',
                'url': reverse('herbapp:round_review', kwargs={'batch_pk': r.batch_id, 'round_no': r.round_no}),
            })

        for e in EnvironmentRecord.objects.filter(is_abnormal=True).select_related('batch').order_by('-record_time'):
            status = 'pending' if not e.handling_opinion else 'handled'
            if status == 'pending':
                level = 'high' if (now - e.record_time).days >= 1 else 'warning'
            else:
                level = 'warning'
            details = list(e.abnormal_details.values()) if isinstance(e.abnormal_details, dict) else []
            warnings.append({
                'id': f'env-{e.pk}',
                'level': level,
                'type': '环境异常',
                'type_en': 'env',
                'batch': e.batch,
                'title': '环境监测参数超标',
                'description': '；'.join(details) if details else str(e.abnormal_details),
                'time': e.record_time,
                'status': status,
                'status_display': '未处理' if status == 'pending' else '已处理',
                'handling': e.handling_opinion,
                'handler': e.recorder,
                'url': reverse('processing:env_record_detail', kwargs={'pk': e.pk}),
                'round_no': e.round_no,
            })

        for eq in EquipmentStatusRecord.objects.filter(is_abnormal=True).select_related('batch', 'equipment').order_by('-record_time'):
            status = 'pending' if not eq.handling_result else 'handled'
            if status == 'pending':
                level = 'critical' if (now - eq.record_time).days >= 1 else 'high'
            else:
                level = 'warning'
            warnings.append({
                'id': f'equip-{eq.pk}',
                'level': level,
                'type': '设备异常',
                'type_en': 'equipment',
                'batch': eq.batch,
                'equipment': eq.equipment,
                'title': f'设备{eq.equipment.equipment_no}状态异常',
                'description': eq.abnormal_description or f'{eq.get_running_status_display()}',
                'time': eq.record_time,
                'status': status,
                'status_display': '未处理' if status == 'pending' else '已处理',
                'handling': eq.handling_result,
                'handler': eq.operator,
                'url': reverse('processing:equipment_status_detail', kwargs={'pk': eq.pk}),
                'round_no': eq.round_no,
            })

        for d in DryingAreaRecord.objects.filter(is_abnormal=True).select_related('batch').order_by('-record_time'):
            status = 'pending' if not d.handling_opinion else 'handled'
            if status == 'pending':
                level = 'high' if (now - d.record_time).days >= 1 else 'warning'
            else:
                level = 'warning'
            details = list(d.abnormal_details.values()) if isinstance(d.abnormal_details, dict) else []
            warnings.append({
                'id': f'drying-{d.pk}',
                'level': level,
                'type': '晾晒区异常',
                'type_en': 'drying',
                'batch': d.batch,
                'title': f'{d.area_name}晾晒条件异常',
                'description': '；'.join(details) if details else str(d.abnormal_details),
                'time': d.record_time,
                'status': status,
                'status_display': '未处理' if status == 'pending' else '已处理',
                'handling': d.handling_opinion,
                'handler': d.recorder,
                'url': reverse('processing:drying_record_detail', kwargs={'pk': d.pk}),
                'round_no': d.round_no,
            })

        for i in InspectionRecord.objects.filter(
            Q(inspection_result='abnormal') | Q(inspection_result='pending')
        ).select_related('batch', 'equipment').order_by('-inspection_time'):
            if i.inspection_result == 'pending':
                status = 'pending'
                level = 'warning'
                desc = '巡检结果待确认'
            else:
                status = 'pending' if not i.handling_result else 'handled'
                if status == 'pending':
                    level = 'high' if (now - i.inspection_time).days >= 1 else 'warning'
                else:
                    level = 'warning'
                desc = i.abnormal_description or '巡检发现异常'
            warnings.append({
                'id': f'inspect-{i.pk}',
                'level': level,
                'type': '巡检异常',
                'type_en': 'inspection',
                'batch': i.batch,
                'equipment': i.equipment,
                'title': f'{i.get_inspection_type_display()}发现问题',
                'description': desc,
                'time': i.inspection_time,
                'status': status,
                'status_display': '待确认' if i.inspection_result == 'pending' else ('未处理' if status == 'pending' else '已处理'),
                'handling': i.handling_result,
                'handler': i.handling_person,
                'url': reverse('processing:inspection_detail', kwargs={'pk': i.pk}),
            })

        for equip in Equipment.objects.filter(status='fault'):
            latest = equip.status_records.filter(is_abnormal=True).order_by('-record_time').first()
            status = 'pending'
            level = 'critical'
            warnings.append({
                'id': f'equipfault-{equip.pk}',
                'level': level,
                'type': '设备故障',
                'type_en': 'equipfault',
                'batch': latest.batch if latest else None,
                'equipment': equip,
                'title': f'设备{equip.equipment_no}处于故障状态',
                'description': f'{equip.equipment_name}状态为故障，需尽快维修并更新状态',
                'time': latest.record_time if latest else equip.created_at,
                'status': status,
                'status_display': '故障未关闭',
                'handling': '',
                'handler': '',
                'url': reverse('processing:equipment_detail', kwargs={'pk': equip.pk}),
            })

        for batch in HerbBatch.objects.filter(status__in=['pending', 'processing']):
            env_records = list(batch.env_records.order_by('-record_time')[:3])
            if len(env_records) >= 2 and all(r.is_abnormal for r in env_records[:2]):
                warnings.append({
                    'id': f'consecutive-env-{batch.pk}',
                    'level': 'critical',
                    'type': '连续超标',
                    'type_en': 'consecutive',
                    'batch': batch,
                    'title': '环境参数连续超标',
                    'description': f'批次{batch.batch_no}连续2次环境监测超标，需立即排查！',
                    'time': env_records[0].record_time,
                    'status': 'pending',
                    'status_display': '待排查',
                    'handling': '',
                    'handler': '',
                    'url': reverse('traceability:batch_trace', kwargs={'pk': batch.pk}),
                })

            rounds = list(batch.rounds.order_by('-round_no')[:3])
            if len(rounds) >= 2 and all(r.is_abnormal for r in rounds[:2]):
                warnings.append({
                    'id': f'consecutive-round-{batch.pk}',
                    'level': 'critical',
                    'type': '连续超标',
                    'type_en': 'consecutive',
                    'batch': batch,
                    'title': '炮制参数连续异常',
                    'description': f'批次{batch.batch_no}连续两轮炮制数据异常，需立即复核！',
                    'time': rounds[0].record_time,
                    'status': 'pending',
                    'status_display': '待排查',
                    'handling': '',
                    'handler': '',
                    'url': reverse('traceability:batch_trace', kwargs={'pk': batch.pk}),
                })

        warnings.sort(key=lambda x: x['time'], reverse=True)
        return warnings


class WarningCenterApi(View):
    def get(self, request):
        view = TraceabilityWarningCenterView()
        all_warnings = view._collect_warnings()

        f_type = request.GET.get('type', '')
        f_level = request.GET.get('level', '')
        f_status = request.GET.get('status', '')
        f_batch = request.GET.get('batch', '')

        if f_type:
            all_warnings = [w for w in all_warnings if w.get('type_en') == f_type]
        if f_level:
            all_warnings = [w for w in all_warnings if w['level'] == f_level]
        if f_status:
            all_warnings = [w for w in all_warnings if w['status'] == f_status]
        if f_batch:
            try:
                bid = int(f_batch)
                all_warnings = [w for w in all_warnings if w.get('batch') and w['batch'].pk == bid]
            except ValueError:
                pass

        summary_data = {
            'critical': sum(1 for w in all_warnings if w['level'] == 'critical'),
            'high': sum(1 for w in all_warnings if w['level'] == 'high'),
            'warning': sum(1 for w in all_warnings if w['level'] == 'warning'),
            'pending': sum(1 for w in all_warnings if w['status'] == 'pending'),
            'handled': sum(1 for w in all_warnings if w['status'] == 'handled'),
            'total': len(all_warnings),
        }

        result = []
        for w in all_warnings[:200]:
            result.append({
                'id': w['id'],
                'level': w['level'],
                'type': w['type'],
                'type_en': w.get('type_en', ''),
                'title': w['title'],
                'description': w['description'],
                'time': w['time'].strftime('%Y-%m-%d %H:%M:%S'),
                'status': w['status'],
                'status_display': w['status_display'],
                'batch_no': w['batch'].batch_no if w.get('batch') else '-',
                'batch_url': reverse('traceability:batch_trace', kwargs={'pk': w['batch'].pk}) if w.get('batch') else '',
                'equipment': w['equipment'].equipment_no if w.get('equipment') else '',
                'handling': w.get('handling', ''),
                'handler': w.get('handler', ''),
                'url': w['url'],
            })

        return JsonResponse({
            'ok': True,
            'warnings': result,
            'summary': summary_data,
        })


class TraceabilityCompareView(TemplateView):
    template_name = 'traceability/compare.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['batches'] = HerbBatch.objects.all().order_by('-created_at')
        ctx['results'] = None

        selected_ids = self.request.GET.getlist('batch_ids', [])
        if not selected_ids and self.request.method == 'GET':
            return ctx

        if self.request.method == 'POST':
            selected_ids = self.request.POST.getlist('batches', [])

        if len(selected_ids) >= 2:
            try:
                ids = [int(x) for x in selected_ids]
                batches = HerbBatch.objects.filter(pk__in=ids)
                if batches.count() >= 2:
                    ctx['results'] = self._build_compare_data(batches)
                    ctx['selected_ids'] = [str(b.pk) for b in batches]
            except (ValueError, TypeError):
                pass

        return ctx

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

    def _build_compare_data(self, batches):
        items = []
        batch_ids = [b.pk for b in batches]

        assessments = BatchQualityAssessment.objects.filter(batch_id__in=batch_ids)
        assess_map = {a.batch_id: a for a in assessments}

        all_round_labels = set()

        for batch in batches:
            rounds = batch.rounds.all().order_by('round_no')
            round_labels = [f'第{r.round_no}轮' for r in rounds]
            all_round_labels.update(round_labels)

            color_map = {'excellent': 100, 'good': 85, 'normal': 70, 'abnormal': 40}
            color_scores = [color_map.get(r.color_rating, 0) for r in rounds]
            weight_loss = [r.get_weight_loss_percent() for r in rounds]
            abnormal_rounds = rounds.filter(is_abnormal=True)

            env_records = batch.env_records.all().order_by('record_time')
            env_temps = [float(r.temperature) for r in env_records if r.temperature]
            env_hums = [float(r.humidity) for r in env_records if r.humidity]

            drying_records = batch.drying_records.all().order_by('record_time')
            drying_temps = [float(r.temperature) for r in drying_records if r.temperature]
            drying_hums = [float(r.humidity) for r in drying_records if r.humidity]

            equip_stats = list(
                batch.equipment_records.values(
                    'equipment__equipment_no', 'equipment__equipment_name'
                ).annotate(
                    total=Count('id'),
                    abnormal=Count('id', filter=Q(is_abnormal=True)),
                )
            )

            inspection_stats = {
                'total': batch.inspection_records.count(),
                'normal': batch.inspection_records.filter(inspection_result='normal').count(),
                'abnormal': batch.inspection_records.filter(inspection_result='abnormal').count(),
                'pending': batch.inspection_records.filter(inspection_result='pending').count(),
            }

            env_abnormal_total = batch.env_records.filter(is_abnormal=True).count()
            equip_abnormal_total = batch.equipment_records.filter(is_abnormal=True).count()
            drying_abnormal_total = batch.drying_records.filter(is_abnormal=True).count()
            inspection_abnormal_total = batch.inspection_records.filter(
                Q(inspection_result='abnormal') | Q(inspection_result='pending')
            ).count()

            assess = assess_map.get(batch.pk)

            items.append({
                'batch': batch,
                'rounds_count': rounds.count(),
                'round_labels': round_labels,
                'color_scores': color_scores,
                'weight_loss_series': weight_loss,
                'final_weight': float(rounds.last().weight) if rounds.exists() else float(batch.initial_weight),
                'total_loss': rounds.last().get_weight_loss_percent() if rounds.exists() else 0,
                'avg_color': round(sum(color_scores) / len(color_scores), 1) if color_scores else 0,
                'abnormal_round_count': abnormal_rounds.count(),
                'env_records_count': env_records.count(),
                'env_abnormal_count': env_abnormal_total,
                'env_temp_avg': round(statistics.mean(env_temps), 2) if env_temps else None,
                'env_temp_std': round(statistics.stdev(env_temps), 2) if len(env_temps) > 1 else 0,
                'env_hum_avg': round(statistics.mean(env_hums), 2) if env_hums else None,
                'env_hum_std': round(statistics.stdev(env_hums), 2) if len(env_hums) > 1 else 0,
                'drying_temp_avg': round(statistics.mean(drying_temps), 2) if drying_temps else None,
                'drying_temp_std': round(statistics.stdev(drying_temps), 2) if len(drying_temps) > 1 else 0,
                'drying_hum_avg': round(statistics.mean(drying_hums), 2) if drying_hums else None,
                'drying_hum_std': round(statistics.stdev(drying_hums), 2) if len(drying_hums) > 1 else 0,
                'equip_stats': equip_stats,
                'equip_abnormal_count': equip_abnormal_total,
                'drying_abnormal_count': drying_abnormal_total,
                'inspection_stats': inspection_stats,
                'inspection_abnormal_count': inspection_abnormal_total,
                'assessment': assess,
                'total_abnormal': (
                    abnormal_rounds.count() + env_abnormal_total +
                    equip_abnormal_total + drying_abnormal_total +
                    inspection_abnormal_total
                ),
            })

        round_labels_sorted = sorted(all_round_labels, key=lambda x: int(x.replace('第', '').replace('轮', '')))

        chart_data = self._build_chart_data(items, round_labels_sorted)
        summary = self._build_summary(items)
        insights = self._build_insights(items, summary)

        return {
            'items': items,
            'chart_data': chart_data,
            'summary': summary,
            'insights': insights,
            'round_labels': round_labels_sorted,
        }

    def _build_chart_data(self, items, round_labels):
        color_palette = ['#8B4513', '#2E8B57', '#B8860B', '#4682B4', '#8A2BE2', '#B22222', '#20B2AA']
        chart_data = {
            'round_labels': ['初始'] + round_labels,
            'batches': [],
            'env_stats': [],
        }

        for i, item in enumerate(items):
            c = color_palette[i % len(color_palette)]
            weight_data = [float(item['batch'].initial_weight)]
            for r in item['batch'].rounds.all().order_by('round_no'):
                weight_data.append(float(r.weight))

            loss_data = [0] + item['weight_loss_series']
            color_data = item['color_scores']

            chart_data['batches'].append({
                'pk': item['batch'].pk,
                'name': item['batch'].batch_no,
                'herb_name': item['batch'].herb_name,
                'color': c,
                'weight': weight_data,
                'loss': loss_data,
                'color_scores': color_data,
                'score': float(item['assessment'].final_score) if item['assessment'] else None,
                'grade': item['assessment'].get_overall_grade_display() if item['assessment'] else '未评估',
                'grade_en': item['assessment'].overall_grade if item['assessment'] else None,
                'abnormal_count': item['abnormal_round_count'],
                'total_abnormal': item['total_abnormal'],
            })

            chart_data['env_stats'].append({
                'name': item['batch'].batch_no,
                'color': c,
                'env_temp_avg': item['env_temp_avg'],
                'env_temp_std': item['env_temp_std'],
                'env_hum_avg': item['env_hum_avg'],
                'env_hum_std': item['env_hum_std'],
                'drying_temp_avg': item['drying_temp_avg'],
                'drying_temp_std': item['drying_temp_std'],
                'drying_hum_avg': item['drying_hum_avg'],
                'drying_hum_std': item['drying_hum_std'],
                'env_abnormal': item['env_abnormal_count'],
                'drying_abnormal': item['drying_abnormal_count'],
                'equip_abnormal': item['equip_abnormal_count'],
                'inspection_abnormal': item['inspection_abnormal_count'],
            })

        return chart_data

    def _build_summary(self, items):
        scored = [i for i in items if i['assessment']]
        if not scored:
            return {
                'count': len(items),
                'best': None, 'worst': None,
                'avg_score': None, 'avg_loss': None,
                'total_abnormal': sum(i['total_abnormal'] for i in items),
            }

        best = max(scored, key=lambda x: float(x['assessment'].final_score))
        worst = min(scored, key=lambda x: float(x['assessment'].final_score))
        avg_score = round(sum(float(i['assessment'].final_score) for i in scored) / len(scored), 2)
        avg_loss = round(sum(i['total_loss'] for i in items) / len(items), 2)

        return {
            'count': len(items),
            'best_batch': best['batch'].batch_no,
            'best_pk': best['batch'].pk,
            'best_score': float(best['assessment'].final_score),
            'worst_batch': worst['batch'].batch_no,
            'worst_pk': worst['batch'].pk,
            'worst_score': float(worst['assessment'].final_score),
            'avg_score': avg_score,
            'avg_loss': avg_loss,
            'total_abnormal': sum(i['total_abnormal'] for i in items),
        }

    def _build_insights(self, items, summary):
        insights = []

        if summary['best_batch'] and summary['worst_batch'] and summary['best_batch'] != summary['worst_batch']:
            diff = round(summary['best_score'] - summary['worst_score'], 2)
            if diff >= 20:
                insights.append({
                    'level': 'danger',
                    'icon': '⚠️',
                    'title': '质量差异显著',
                    'content': f'最佳批次{summary["best_batch"]}与待提升批次{summary["worst_batch"]}评分差距达{diff}分，建议重点分析工艺稳定性。',
                })

        high_env_std = []
        for item in items:
            if item['env_temp_std'] and item['env_temp_std'] > 3:
                high_env_std.append(item['batch'].batch_no)
        if high_env_std:
            insights.append({
                'level': 'warning',
                'icon': '🌡️',
                'title': '环境波动较大',
                'content': f'批次{",".join(high_env_std)}的环境温度标准差超过3°C，环境控制不稳定可能是质量波动原因。',
            })

        high_loss = []
        for item in items:
            if item['total_loss'] > 20:
                high_loss.append(f"{item['batch'].batch_no}({item['total_loss']}%)")
        if high_loss:
            insights.append({
                'level': 'warning',
                'icon': '⚖️',
                'title': '重量损耗超标',
                'content': f'批次{",".join(high_loss)}的重量损耗超过20%阈值，需检查蒸制/晾晒参数是否符合标准。',
            })

        high_abnormal = sorted(items, key=lambda x: x['total_abnormal'], reverse=True)
        if high_abnormal and high_abnormal[0]['total_abnormal'] > 0:
            top = high_abnormal[0]
            insights.append({
                'level': 'info' if top['total_abnormal'] < 5 else 'warning',
                'icon': '🔔',
                'title': '异常发生频次',
                'content': f'批次{top["batch"].batch_no}发生异常最多，共{top["total_abnormal"]}次（炮制{top["abnormal_round_count"]}次、环境{top["env_abnormal_count"]}次、设备{top["equip_abnormal_count"]}次），建议追溯具体环节。',
            })

        equip_issue = []
        for item in items:
            if item['equip_abnormal_count'] > 0 or item['equip_stats']:
                bad_eq = [e for e in item['equip_stats'] if e['abnormal'] > 0]
                if bad_eq:
                    names = [f"{e['equipment__equipment_no']}" for e in bad_eq]
                    equip_issue.append(f"{item['batch'].batch_no}使用设备：{','.join(names)}")
        if equip_issue:
            insights.append({
                'level': 'warning',
                'icon': '⚙️',
                'title': '设备影响分析',
                'content': f'设备异常可能影响质量：{"；".join(equip_issue)}。建议检查设备校准记录和维护情况。',
            })

        return insights


class TraceabilityCompareApi(View):
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

        view = TraceabilityCompareView()
        results = view._build_compare_data(batches)

        return JsonResponse({
            'ok': True,
            'chart_data': results['chart_data'],
            'summary': results['summary'],
            'insights': results['insights'],
        })
