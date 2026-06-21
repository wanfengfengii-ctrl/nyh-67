import json

from django.contrib import messages
from django.db import models as db_models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView, DetailView, FormView, ListView, TemplateView, UpdateView,
)

from herbapp.models import HerbBatch, ProcessingStandardTemplate, RoundStandard
from processing.models import EnvironmentStandard, Equipment

from .forms import (
    AcceptanceRuleStandardForm, ChangeRequestForm, ChangeRequestPublishForm,
    ChangeRequestReviewForm, EquipmentOperationStandardForm,
    QualityFluctuationAnalysisForm, QualityReviewForm, VersionCompareForm,
)
from .models import (
    AcceptanceRuleStandard, ApprovalRecord, BatchProcessVersionLink,
    ChangeRequest, EquipmentOperationStandard, ProcessVersionSnapshot,
    QualityFluctuationAnalysis,
)


STANDARD_TYPE_MAP = {
    'processing_template': {
        'model': ProcessingStandardTemplate,
        'name': '炮制标准模板',
        'name_field': 'template_name',
    },
    'environment_standard': {
        'model': EnvironmentStandard,
        'name': '环境参数标准',
        'name_field': 'herb_name',
    },
    'equipment_operation': {
        'model': EquipmentOperationStandard,
        'name': '设备操作要求',
        'name_field': 'operation_name',
    },
    'acceptance_rule': {
        'model': AcceptanceRuleStandard,
        'name': '验收规则',
        'name_field': 'rule_name',
    },
}


def _get_standard_snapshot(standard_type, standard_id, include_related=True):
    info = STANDARD_TYPE_MAP.get(standard_type)
    if not info or not standard_id:
        return {}
    try:
        obj = info['model'].objects.get(pk=standard_id)
    except info['model'].DoesNotExist:
        return {}
    snap = {}
    if hasattr(obj, 'make_version_snapshot'):
        snap = obj.make_version_snapshot()
    else:
        fields = [f.name for f in info['model']._meta.get_fields()
                  if f.concrete and not f.is_relation]
        for f in fields:
            v = getattr(obj, f)
            snap[f] = str(v) if hasattr(v, 'quantize') else v
    return snap


class DashboardView(TemplateView):
    template_name = 'version_control/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_changes'] = ChangeRequest.objects.filter(
            status__in=[ChangeRequest.STATUS_SUBMITTED, ChangeRequest.STATUS_REVIEWING]
        ).count()
        ctx['total_changes'] = ChangeRequest.objects.count()
        ctx['approved_changes'] = ChangeRequest.objects.filter(
            status=ChangeRequest.STATUS_PUBLISHED
        ).count()
        ctx['recent_changes'] = ChangeRequest.objects.all()[:10]
        ctx['template_versions'] = ProcessingStandardTemplate.objects.values(
            'version_status'
        ).annotate(count=db_models.Count('pk'))
        ctx['total_equipment_ops'] = EquipmentOperationStandard.objects.filter(
            is_current=True
        ).count()
        ctx['total_acceptance_rules'] = AcceptanceRuleStandard.objects.filter(
            is_current=True
        ).count()
        ctx['recent_analyses'] = QualityFluctuationAnalysis.objects.filter(
            status=QualityFluctuationAnalysis.ANALYSIS_STATUS_COMPLETED
        )[:5]
        return ctx


class ChangeRequestListView(ListView):
    model = ChangeRequest
    template_name = 'version_control/change_list.html'
    context_object_name = 'changes'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        std_type = self.request.GET.get('standard_type')
        if std_type:
            qs = qs.filter(standard_type=std_type)
        change_type = self.request.GET.get('change_type')
        if change_type:
            qs = qs.filter(change_type=change_type)
        keyword = self.request.GET.get('q')
        if keyword:
            qs = qs.filter(
                db_models.Q(title__icontains=keyword)
                | db_models.Q(request_no__icontains=keyword)
                | db_models.Q(change_reason__icontains=keyword)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_list'] = ChangeRequest.STATUS_CHOICES
        ctx['standard_types'] = STANDARD_TYPE_MAP
        ctx['change_types'] = ChangeRequest.CHANGE_TYPE_CHOICES
        ctx['current_status'] = self.request.GET.get('status', '')
        ctx['current_standard_type'] = self.request.GET.get('standard_type', '')
        ctx['current_change_type'] = self.request.GET.get('change_type', '')
        ctx['keyword'] = self.request.GET.get('q', '')
        return ctx


class ChangeRequestDetailView(DetailView):
    model = ChangeRequest
    template_name = 'version_control/change_detail.html'
    context_object_name = 'change'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        obj = self.object
        ctx['approval_records'] = obj.approval_records.all()
        ctx['standard_type_info'] = STANDARD_TYPE_MAP.get(obj.standard_type, {})
        try:
            ctx['source_object'] = obj.get_standard_object('source')
        except Exception:
            ctx['source_object'] = None
        try:
            ctx['target_object'] = obj.get_standard_object('target')
        except Exception:
            ctx['target_object'] = None
        if not obj.changed_fields and (obj.change_content_before or obj.change_content_after):
            ctx['computed_diffs'] = obj.compute_field_diffs()
        else:
            ctx['computed_diffs'] = obj.changed_fields or []
        ctx['quality_analyses'] = obj.quality_analyses.all()
        ctx['review_form'] = ChangeRequestReviewForm()
        ctx['publish_form'] = ChangeRequestPublishForm(
            initial={'effective_date': obj.effective_date}
        )
        return ctx


class ChangeRequestCreateView(CreateView):
    model = ChangeRequest
    form_class = ChangeRequestForm
    template_name = 'version_control/change_form.html'

    def get_initial(self):
        initial = super().get_initial()
        std_type = self.request.GET.get('standard_type')
        if std_type:
            initial['standard_type'] = std_type
        src_id = self.request.GET.get('source_id')
        if src_id:
            initial['source_standard_id'] = int(src_id)
            info = STANDARD_TYPE_MAP.get(std_type)
            if info:
                try:
                    src = info['model'].objects.get(pk=int(src_id))
                    version = getattr(src, 'version_code', '')
                    initial['source_version_code'] = version
                    name_field = info.get('name_field')
                    if name_field:
                        name = getattr(src, name_field, '')
                        initial['title'] = f'修改{info["name"]} - {name}'
                except Exception:
                    pass
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.status = ChangeRequest.STATUS_DRAFT
        if not obj.applicant:
            obj.applicant = '匿名用户'
        if obj.source_standard_id:
            obj.change_content_before = _get_standard_snapshot(
                obj.standard_type, obj.source_standard_id
            )
            info = STANDARD_TYPE_MAP.get(obj.standard_type)
            if info:
                try:
                    src = info['model'].objects.get(pk=obj.source_standard_id)
                    obj.source_version_code = getattr(src, 'version_code', '')
                except Exception:
                    pass
        obj.save()
        obj.add_approval_record(
            ApprovalRecord.ACTION_SUBMIT if False else ApprovalRecord.ACTION_COMMENT,
            obj.applicant,
            '创建变更申请草稿'
        )
        messages.success(self.request, '变更申请已创建')
        return redirect(reverse('version_control:change_detail', args=[obj.pk]))


class ChangeRequestSubmitView(View):
    def post(self, request, pk):
        change = get_object_or_404(ChangeRequest, pk=pk)
        if change.status != ChangeRequest.STATUS_DRAFT:
            messages.error(request, '只有草稿状态可以提交')
            return redirect(reverse('version_control:change_detail', args=[pk]))
        applicant = request.POST.get('applicant') or change.applicant or '匿名用户'
        if change.source_standard_id and not change.change_content_before:
            change.change_content_before = _get_standard_snapshot(
                change.standard_type, change.source_standard_id
            )
        change.compute_field_diffs()
        change.status = ChangeRequest.STATUS_SUBMITTED
        change.save()
        change.add_approval_record(
            ApprovalRecord.ACTION_SUBMIT, applicant, '提交变更申请',
            previous_status=ChangeRequest.STATUS_DRAFT,
            new_status=ChangeRequest.STATUS_SUBMITTED,
        )
        messages.success(request, '变更申请已提交，等待审核')
        return redirect(reverse('version_control:change_detail', args=[pk]))


class ChangeRequestCancelView(View):
    def post(self, request, pk):
        change = get_object_or_404(ChangeRequest, pk=pk)
        if change.status in [ChangeRequest.STATUS_APPROVED, ChangeRequest.STATUS_PUBLISHED]:
            messages.error(request, '已通过或已发布的申请无法撤销')
            return redirect(reverse('version_control:change_detail', args=[pk]))
        applicant = request.POST.get('applicant') or change.applicant or '匿名用户'
        prev = change.status
        change.status = ChangeRequest.STATUS_CANCELLED
        change.save()
        change.add_approval_record(
            ApprovalRecord.ACTION_CANCEL, applicant,
            request.POST.get('remark', '撤销变更申请'),
            previous_status=prev, new_status=ChangeRequest.STATUS_CANCELLED,
        )
        messages.success(request, '变更申请已撤销')
        return redirect(reverse('version_control:change_detail', args=[pk]))


class ChangeRequestReviewView(View):
    def post(self, request, pk):
        change = get_object_or_404(ChangeRequest, pk=pk)
        form = ChangeRequestReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, '表单无效')
            return redirect(reverse('version_control:change_detail', args=[pk]))
        action = form.cleaned_data['action']
        reviewer = form.cleaned_data['reviewer']
        remark = form.cleaned_data['remark']
        prev = change.status

        if action == 'approve':
            if change.status not in [ChangeRequest.STATUS_SUBMITTED, ChangeRequest.STATUS_REVIEWING]:
                messages.error(request, '当前状态无法审核通过')
                return redirect(reverse('version_control:change_detail', args=[pk]))
            change.status = ChangeRequest.STATUS_APPROVED
            change.approver = reviewer
            change.approved_at = timezone.now()
            change.approval_remark = remark
            change.save()
            change.add_approval_record(
                ApprovalRecord.ACTION_APPROVE, reviewer, remark,
                previous_status=prev, new_status=ChangeRequest.STATUS_APPROVED,
            )
            messages.success(request, '变更申请已审核通过，可进行发布')

        elif action == 'reject':
            if change.status not in [ChangeRequest.STATUS_SUBMITTED, ChangeRequest.STATUS_REVIEWING]:
                messages.error(request, '当前状态无法驳回')
                return redirect(reverse('version_control:change_detail', args=[pk]))
            change.status = ChangeRequest.STATUS_REJECTED
            change.approver = reviewer
            change.approved_at = timezone.now()
            change.approval_remark = remark
            change.save()
            change.add_approval_record(
                ApprovalRecord.ACTION_REJECT, reviewer, remark,
                previous_status=prev, new_status=ChangeRequest.STATUS_REJECTED,
            )
            messages.warning(request, '变更申请已被驳回')

        elif action == 'comment':
            change.add_approval_record(
                ApprovalRecord.ACTION_COMMENT, reviewer, remark,
            )
            messages.success(request, '备注已添加')

        return redirect(reverse('version_control:change_detail', args=[pk]))


class ChangeRequestPublishView(View):
    def post(self, request, pk):
        change = get_object_or_404(ChangeRequest, pk=pk)
        form = ChangeRequestPublishForm(request.POST)
        if not form.is_valid():
            messages.error(request, '表单无效')
            return redirect(reverse('version_control:change_detail', args=[pk]))
        if change.status != ChangeRequest.STATUS_APPROVED:
            messages.error(request, '只有已审核通过的申请可以发布')
            return redirect(reverse('version_control:change_detail', args=[pk]))

        publisher = form.cleaned_data['publisher']
        publish_remark = form.cleaned_data['publish_remark']
        effective_date = form.cleaned_data.get('effective_date')
        if effective_date:
            change.effective_date = effective_date

        info = STANDARD_TYPE_MAP.get(change.standard_type)
        new_standard = None
        model = info.get('model') if info else None

        if change.change_type in [ChangeRequest.CHANGE_TYPE_CREATE, ChangeRequest.CHANGE_TYPE_MODIFY]:
            if model and change.change_content_after:
                new_standard = self._create_new_version(model, change)
                if new_standard:
                    change.target_standard_id = new_standard.pk

        if change.change_type == ChangeRequest.CHANGE_TYPE_OBSOLETE:
            if model and change.source_standard_id:
                try:
                    src = model.objects.get(pk=change.source_standard_id)
                    if hasattr(src, 'version_status'):
                        src.version_status = getattr(model, 'VERSION_STATUS_OBSOLETE', 'obsolete')
                    if hasattr(src, 'is_active'):
                        src.is_active = False
                    if hasattr(src, 'is_current'):
                        src.is_current = False
                    src.save()
                except Exception:
                    pass

        if change.change_type == ChangeRequest.CHANGE_TYPE_MODIFY and change.source_standard_id:
            if model:
                try:
                    src = model.objects.get(pk=change.source_standard_id)
                    if hasattr(src, 'is_current'):
                        src.is_current = False
                        if hasattr(src, 'version_status'):
                            src.version_status = getattr(model, 'VERSION_STATUS_OBSOLETE', 'obsolete')
                        src.save()
                    if new_standard and hasattr(new_standard, 'master_id'):
                        if src.master_id:
                            new_standard.master_id = src.master_id
                        else:
                            new_standard.master_id = src.pk
                        new_standard.save()
                except Exception:
                    pass

        change.status = ChangeRequest.STATUS_PUBLISHED
        change.publisher = publisher
        change.published_at = timezone.now()
        change.publish_remark = publish_remark
        change.save()
        change.add_approval_record(
            ApprovalRecord.ACTION_PUBLISH, publisher, publish_remark,
            previous_status=ChangeRequest.STATUS_APPROVED,
            new_status=ChangeRequest.STATUS_PUBLISHED,
        )
        messages.success(request, '变更已成功发布，新版本已生效')
        return redirect(reverse('version_control:change_detail', args=[pk]))

    def _create_new_version(self, model, change):
        content = change.change_content_after or {}
        data = {}
        fields_map = {f.name: f for f in model._meta.get_fields() if f.concrete}
        for key, val in content.items():
            if key not in fields_map:
                continue
            f = fields_map[key]
            try:
                internal_type = f.get_internal_type()
                if internal_type in ('DecimalField', 'FloatField') and val is not None:
                    data[key] = f.to_python(val)
                elif internal_type == 'BooleanField':
                    data[key] = bool(val) if isinstance(val, str) else val
                elif internal_type == 'ForeignKey':
                    if val is not None:
                        try:
                            data[key + '_id'] = int(val)
                        except (TypeError, ValueError):
                            pass
                else:
                    data[key] = val
            except Exception:
                continue
        if 'version_major' not in data and 'version_minor' not in data:
            src_ver_major = 1
            src_ver_minor = 0
            if change.source_standard_id:
                try:
                    src = model.objects.get(pk=change.source_standard_id)
                    src_ver_major = getattr(src, 'version_major', 1)
                    src_ver_minor = getattr(src, 'version_minor', 0)
                except Exception:
                    pass
            data['version_major'] = src_ver_major
            data['version_minor'] = src_ver_minor + 1
        if 'is_current' in fields_map:
            data['is_current'] = True
        if 'version_status' in fields_map:
            data['version_status'] = getattr(model, 'VERSION_STATUS_APPROVED', 'approved')
        if 'is_active' in fields_map:
            data['is_active'] = True
        data['version_created_by'] = change.publisher or change.applicant
        data['version_created_at'] = timezone.now()
        try:
            new_obj = model.objects.create(**data)
            if change.standard_type == 'processing_template':
                rounds = (change.change_content_after or {}).get('round_standards', [])
                for r in rounds:
                    rs_data = {
                        'template': new_obj,
                        'round_no': r.get('round_no'),
                    }
                    for k in ['steam_time_min', 'steam_time_max', 'dry_duration_min',
                              'dry_duration_max', 'weight_loss_max']:
                        v = r.get(k)
                        if v not in (None, ''):
                            rs_data[k] = v
                    if r.get('required_color'):
                        rs_data['required_color'] = r.get('required_color')
                    try:
                        RoundStandard.objects.create(**rs_data)
                    except Exception:
                        pass
            return new_obj
        except Exception as e:
            messages.warning(self.request, f'创建新版本时出现警告: {e}')
            return None


class VersionCompareView(TemplateView):
    template_name = 'version_control/version_compare.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = VersionCompareForm(self.request.GET)
        ctx['form'] = form
        ctx['result'] = None
        ctx['standard_types'] = STANDARD_TYPE_MAP
        if form.is_valid() and form.has_changed():
            std_type = form.cleaned_data.get('standard_type')
            id_left = form.cleaned_data.get('id_left')
            id_right = form.cleaned_data.get('id_right')
            ver_left = form.cleaned_data.get('version_left')
            ver_right = form.cleaned_data.get('version_right')
            master_id = form.cleaned_data.get('master_id')
            info = STANDARD_TYPE_MAP.get(std_type)
            if info and (id_left or ver_left) and (id_right or ver_right):
                model = info['model']
                obj_left, obj_right = None, None
                if id_left:
                    try:
                        obj_left = model.objects.get(pk=id_left)
                    except model.DoesNotExist:
                        pass
                if id_right:
                    try:
                        obj_right = model.objects.get(pk=id_right)
                    except model.DoesNotExist:
                        pass
                if not obj_left and ver_left:
                    qs = model.objects.all()
                    if master_id:
                        qs = qs.filter(
                            db_models.Q(pk=master_id) | db_models.Q(master_id=master_id)
                        )
                    obj_left = qs.filter(version_code=ver_left).first()
                if not obj_right and ver_right:
                    qs = model.objects.all()
                    if master_id:
                        qs = qs.filter(
                            db_models.Q(pk=master_id) | db_models.Q(master_id=master_id)
                        )
                    obj_right = qs.filter(version_code=ver_right).first()
                snap_left = {}
                snap_right = {}
                if hasattr(obj_left, 'make_version_snapshot'):
                    snap_left = obj_left.make_version_snapshot()
                elif obj_left:
                    for f in model._meta.get_fields():
                        if f.concrete and not f.is_relation:
                            v = getattr(obj_left, f.name)
                            snap_left[f.name] = str(v) if hasattr(v, 'quantize') else v
                if hasattr(obj_right, 'make_version_snapshot'):
                    snap_right = obj_right.make_version_snapshot()
                elif obj_right:
                    for f in model._meta.get_fields():
                        if f.concrete and not f.is_relation:
                            v = getattr(obj_right, f.name)
                            snap_right[f.name] = str(v) if hasattr(v, 'quantize') else v
                all_keys = set(list(snap_left.keys()) + list(snap_right.keys()))
                field_labels = {
                    'template_name': '模板名称',
                    'herb_name': '适用药材',
                    'total_rounds': '总轮次数',
                    'description': '模板说明',
                    'version_code': '版本号',
                    'version_major': '主版本号',
                    'version_minor': '次版本号',
                    'round_standards': '轮次标准',
                    'round_no': '轮次序号',
                    'steam_time_min': '蒸制时间下限',
                    'steam_time_max': '蒸制时间上限',
                    'dry_duration_min': '晾晒时长下限',
                    'dry_duration_max': '晾晒时长上限',
                    'weight_loss_max': '最大允许重量损耗(%)',
                    'required_color': '色泽要求',
                    'param_type': '参数类型',
                    'stage': '适用阶段',
                    'min_value': '最小值',
                    'max_value': '最大值',
                    'unit': '单位',
                    'operation_stage': '操作阶段',
                    'operation_name': '操作项目名称',
                    'operation_steps': '操作步骤说明',
                    'key_param_name': '关键参数名称',
                    'key_param_min': '关键参数下限',
                    'key_param_max': '关键参数上限',
                    'key_param_unit': '参数单位',
                    'param_severity': '参数严重等级',
                    'safety_requirements': '安全注意事项',
                    'quality_checkpoints': '质量检查点',
                    'rule_name': '规则名称',
                    'rule_type': '规则类型',
                    'rule_description': '规则描述',
                    'threshold_min': '阈值下限',
                    'threshold_max': '阈值上限',
                    'result_if_violated': '违反规则结论',
                    'weight_in_comprehensive': '综合评分权重(%)',
                    'handling_advice': '异常处理建议',
                }
                diffs = []
                for k in sorted(all_keys):
                    left = snap_left.get(k)
                    right = snap_right.get(k)
                    if k == 'round_standards':
                        left_rounds = {r['round_no']: r for r in (left or [])}
                        right_rounds = {r['round_no']: r for r in (right or [])}
                        all_rnos = set(left_rounds) | set(right_rounds)
                        for rn in sorted(all_rnos):
                            lr = left_rounds.get(rn, {})
                            rr = right_rounds.get(rn, {})
                            for field in ['steam_time_min', 'steam_time_max',
                                          'dry_duration_min', 'dry_duration_max',
                                          'weight_loss_max', 'required_color']:
                                lv = lr.get(field)
                                rv = rr.get(field)
                                if lv != rv:
                                    diffs.append({
                                        'field': f'轮次{rn}-{field_labels.get(field, field)}',
                                        'left': lv,
                                        'right': rv,
                                        'changed': True,
                                    })
                        continue
                    if isinstance(left, (list, dict)) or isinstance(right, (list, dict)):
                        left_str = json.dumps(left, ensure_ascii=False, indent=2) if left else ''
                        right_str = json.dumps(right, ensure_ascii=False, indent=2) if right else ''
                        changed = left_str != right_str
                    else:
                        changed = left != right
                    diffs.append({
                        'field': field_labels.get(k, k),
                        'left': left,
                        'right': right,
                        'changed': changed,
                    })
                ctx['result'] = {
                    'standard_type': std_type,
                    'standard_type_name': info.get('name', ''),
                    'left': {
                        'id': getattr(obj_left, 'pk', None),
                        'version': getattr(obj_left, 'version_code', ''),
                        'name': str(obj_left) if obj_left else '',
                    },
                    'right': {
                        'id': getattr(obj_right, 'pk', None),
                        'version': getattr(obj_right, 'version_code', ''),
                        'name': str(obj_right) if obj_right else '',
                    },
                    'diffs': diffs,
                }
                ctx['available_versions'] = []
                if std_type and info:
                    model = info['model']
                    qs = model.objects.all()
                    if master_id:
                        qs = qs.filter(
                            db_models.Q(pk=master_id) | db_models.Q(master_id=master_id)
                        )
                    ctx['available_versions'] = qs.order_by(
                        'version_major', 'version_minor'
                    ).values('pk', 'version_code', 'version_status', 'is_current')
        return ctx


class StandardHistoryView(TemplateView):
    template_name = 'version_control/standard_history.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        std_type = self.request.GET.get('standard_type')
        master_id = self.request.GET.get('master_id')
        ctx['standard_types'] = STANDARD_TYPE_MAP
        ctx['current_standard_type'] = std_type or ''
        ctx['master_id'] = master_id or ''
        ctx['history'] = []
        info = STANDARD_TYPE_MAP.get(std_type)
        if info and master_id:
            model = info['model']
            qs = model.objects.filter(
                db_models.Q(pk=int(master_id)) | db_models.Q(master_id=int(master_id))
            ).order_by('version_major', 'version_minor', '-created_at')
            ctx['history'] = qs
            ctx['current_master'] = qs.filter(
                is_current=True
            ).first() or qs.first()
        return ctx


class BatchVersionView(TemplateView):
    template_name = 'version_control/batch_version.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        batch_no = self.request.GET.get('batch_no')
        batch_id = self.request.GET.get('batch_id')
        ctx['batch_no'] = batch_no or ''
        ctx['batch_id'] = batch_id or ''
        ctx['link'] = None
        ctx['batch'] = None
        batch = None
        if batch_id:
            try:
                batch = HerbBatch.objects.get(pk=int(batch_id))
            except (HerbBatch.DoesNotExist, ValueError):
                pass
        elif batch_no:
            try:
                batch = HerbBatch.objects.get(batch_no=batch_no)
            except HerbBatch.DoesNotExist:
                pass
        if batch:
            ctx['batch'] = batch
            try:
                ctx['link'] = batch.process_version_link
            except BatchProcessVersionLink.DoesNotExist:
                ctx['link'] = None
        return ctx


class LinkBatchToVersionView(View):
    def post(self, request):
        batch_id = request.POST.get('batch_id')
        user = request.POST.get('user') or '系统'
        snapshot_id = request.POST.get('snapshot_id')
        if not batch_id:
            messages.error(request, '缺少批次ID')
            return redirect(reverse('version_control:batch_version') + f'?batch_id={batch_id}')
        try:
            batch = HerbBatch.objects.get(pk=int(batch_id))
        except (HerbBatch.DoesNotExist, ValueError):
            messages.error(request, '批次不存在')
            return redirect(reverse('version_control:batch_version'))
        snapshot = None
        if snapshot_id:
            try:
                snapshot = ProcessVersionSnapshot.objects.get(pk=int(snapshot_id))
            except (ProcessVersionSnapshot.DoesNotExist, ValueError):
                pass
        link = BatchProcessVersionLink.link_batch_to_current(batch, user, snapshot)
        messages.success(request, '批次已关联到当前工艺版本')
        return redirect(reverse('version_control:batch_version') + f'?batch_id={batch.pk}')


class EquipmentOpListView(ListView):
    model = EquipmentOperationStandard
    template_name = 'version_control/equipment_op_list.html'
    context_object_name = 'standards'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        stage = self.request.GET.get('stage')
        if stage:
            qs = qs.filter(operation_stage=stage)
        herb = self.request.GET.get('herb_name')
        if herb:
            qs = qs.filter(herb_name__icontains=herb)
        severity = self.request.GET.get('severity')
        if severity:
            qs = qs.filter(param_severity=severity)
        status = self.request.GET.get('version_status')
        if status:
            qs = qs.filter(version_status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['stages'] = EquipmentOperationStandard.STAGE_CHOICES
        ctx['severities'] = EquipmentOperationStandard.SEVERITY_CHOICES
        ctx['version_statuses'] = EquipmentOperationStandard.VERSION_STATUS_CHOICES
        return ctx


class EquipmentOpCreateView(CreateView):
    model = EquipmentOperationStandard
    form_class = EquipmentOperationStandardForm
    template_name = 'version_control/equipment_op_form.html'
    success_url = reverse_lazy('version_control:equipment_op_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['version_status'] = EquipmentOperationStandard.VERSION_STATUS_APPROVED
        initial['is_current'] = True
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        if not obj.version_created_by:
            obj.version_created_by = '创建人'
        messages.success(self.request, '设备操作要求已创建')
        return super().form_valid(form)


class EquipmentOpDetailView(DetailView):
    model = EquipmentOperationStandard
    template_name = 'version_control/equipment_op_detail.html'
    context_object_name = 'standard'


class AcceptanceRuleListView(ListView):
    model = AcceptanceRuleStandard
    template_name = 'version_control/acceptance_rule_list.html'
    context_object_name = 'standards'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        rtype = self.request.GET.get('rule_type')
        if rtype:
            qs = qs.filter(rule_type=rtype)
        herb = self.request.GET.get('herb_name')
        if herb:
            qs = qs.filter(herb_name__icontains=herb)
        status = self.request.GET.get('version_status')
        if status:
            qs = qs.filter(version_status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['rule_types'] = AcceptanceRuleStandard.RULE_TYPE_CHOICES
        ctx['version_statuses'] = AcceptanceRuleStandard.VERSION_STATUS_CHOICES
        return ctx


class AcceptanceRuleCreateView(CreateView):
    model = AcceptanceRuleStandard
    form_class = AcceptanceRuleStandardForm
    template_name = 'version_control/acceptance_rule_form.html'
    success_url = reverse_lazy('version_control:acceptance_rule_list')

    def get_initial(self):
        initial = super().get_initial()
        initial['version_status'] = AcceptanceRuleStandard.VERSION_STATUS_APPROVED
        initial['is_current'] = True
        return initial

    def form_valid(self, form):
        obj = form.save(commit=False)
        if not obj.version_created_by:
            obj.version_created_by = '创建人'
        messages.success(self.request, '验收规则已创建')
        return super().form_valid(form)


class AcceptanceRuleDetailView(DetailView):
    model = AcceptanceRuleStandard
    template_name = 'version_control/acceptance_rule_detail.html'
    context_object_name = 'standard'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['related_templates'] = []
        if self.object.template_id:
            ctx['related_templates'].append(self.object.template)
        return ctx


class SnapshotListView(ListView):
    model = ProcessVersionSnapshot
    template_name = 'version_control/snapshot_list.html'
    context_object_name = 'snapshots'
    paginate_by = 20
    ordering = ['-created_at']


class SnapshotCreateView(CreateView):
    model = ProcessVersionSnapshot
    fields = ['snapshot_name', 'description', 'template_id', 'is_active']
    template_name = 'version_control/snapshot_form.html'
    success_url = reverse_lazy('version_control:snapshot_list')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.created_by = self.request.POST.get('created_by', '创建人')
        try:
            if obj.template_id:
                tpl = ProcessingStandardTemplate.objects.get(pk=obj.template_id)
                obj.template_version = getattr(tpl, 'version_code', '')
                obj.template_snapshot = {
                    'template_name': tpl.template_name,
                    'herb_name': tpl.herb_name,
                    'total_rounds': tpl.total_rounds,
                    'description': tpl.description,
                }
                rounds = []
                for rs in tpl.round_standards.all():
                    rounds.append({
                        'round_no': rs.round_no,
                        'steam_time_min': str(rs.steam_time_min),
                        'steam_time_max': str(rs.steam_time_max),
                        'dry_duration_min': str(rs.dry_duration_min),
                        'dry_duration_max': str(rs.dry_duration_max),
                        'weight_loss_max': str(rs.weight_loss_max),
                        'required_color': rs.required_color,
                    })
                obj.round_standards_snapshot = rounds
                env_ids = []
                env_snaps = []
                for es in EnvironmentStandard.objects.filter(
                    herb_name=tpl.herb_name, is_active=True
                ):
                    env_ids.append(es.pk)
                    env_snaps.append(es.make_version_snapshot())
                obj.env_standard_ids = env_ids
                obj.env_standards_snapshot = env_snaps
        except Exception as e:
            messages.warning(self.request, f'部分快照数据生成失败: {e}')
        obj.save()
        messages.success(self.request, '工艺版本快照已创建')
        return super().form_valid(form)


class SnapshotDetailView(DetailView):
    model = ProcessVersionSnapshot
    template_name = 'version_control/snapshot_detail.html'
    context_object_name = 'snapshot'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['related_batches'] = self.object.batch_links.all()
        return ctx


class QualityAnalysisListView(ListView):
    model = QualityFluctuationAnalysis
    template_name = 'version_control/quality_list.html'
    context_object_name = 'analyses'
    paginate_by = 20
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        trend = self.request.GET.get('overall_trend')
        if trend:
            qs = qs.filter(overall_trend=trend)
        herb = self.request.GET.get('herb_name')
        if herb:
            qs = qs.filter(herb_name__icontains=herb)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['statuses'] = QualityFluctuationAnalysis.STATUS_CHOICES
        ctx['trends'] = QualityFluctuationAnalysis.TREND_CHOICES
        return ctx


class QualityAnalysisCreateView(CreateView):
    model = QualityFluctuationAnalysis
    form_class = QualityFluctuationAnalysisForm
    template_name = 'version_control/quality_form.html'
    success_url = reverse_lazy('version_control:quality_list')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.save()
        messages.success(self.request, '质量波动分析记录已创建')
        return redirect(reverse('version_control:quality_detail', args=[obj.pk]))


class QualityAnalysisDetailView(DetailView):
    model = QualityFluctuationAnalysis
    template_name = 'version_control/quality_detail.html'
    context_object_name = 'analysis'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['review_form'] = QualityReviewForm()
        return ctx


class QualityAnalysisRunView(View):
    def post(self, request, pk):
        analysis = get_object_or_404(QualityFluctuationAnalysis, pk=pk)
        try:
            analysis.run_analysis()
            messages.success(request, '质量波动分析已完成')
        except Exception as e:
            messages.error(request, f'分析失败: {e}')
        return redirect(reverse('version_control:quality_detail', args=[pk]))


class QualityAnalysisReviewView(View):
    def post(self, request, pk):
        analysis = get_object_or_404(QualityFluctuationAnalysis, pk=pk)
        form = QualityReviewForm(request.POST)
        if not form.is_valid():
            messages.error(request, '表单无效')
            return redirect(reverse('version_control:quality_detail', args=[pk]))
        analysis.reviewed_by = form.cleaned_data['reviewed_by']
        analysis.review_remark = form.cleaned_data['review_remark']
        analysis.reviewed_at = timezone.now()
        analysis.status = QualityFluctuationAnalysis.ANALYSIS_STATUS_REVIEWED
        analysis.save()
        messages.success(request, '分析已复核')
        return redirect(reverse('version_control:quality_detail', args=[pk]))
