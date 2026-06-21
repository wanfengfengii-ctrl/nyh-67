import copy
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from herbapp.models import HerbBatch, ProcessingStandardTemplate, RoundStandard
from processing.models import EnvironmentStandard, Equipment


class VersionControlMixin(models.Model):
    VERSION_STATUS_DRAFT = 'draft'
    VERSION_STATUS_PENDING = 'pending'
    VERSION_STATUS_APPROVED = 'approved'
    VERSION_STATUS_OBSOLETE = 'obsolete'

    VERSION_STATUS_CHOICES = [
        (VERSION_STATUS_DRAFT, '草稿'),
        (VERSION_STATUS_PENDING, '待审批'),
        (VERSION_STATUS_APPROVED, '已批准'),
        (VERSION_STATUS_OBSOLETE, '已废弃'),
    ]

    version_code = models.CharField('版本号', max_length=30, blank=True, null=True)
    version_major = models.PositiveIntegerField('主版本号', default=1)
    version_minor = models.PositiveIntegerField('次版本号', default=0)
    version_status = models.CharField(
        '版本状态', max_length=20, choices=VERSION_STATUS_CHOICES,
        default=VERSION_STATUS_DRAFT
    )
    master_id = models.PositiveIntegerField('主记录ID', blank=True, null=True)
    is_current = models.BooleanField('是否当前版本', default=False)
    version_remark = models.TextField('版本说明', blank=True, null=True)
    version_created_at = models.DateTimeField('版本创建时间', blank=True, null=True)
    version_created_by = models.CharField('版本创建人', max_length=50, blank=True, null=True)

    class Meta:
        abstract = True

    def save_version_code(self):
        self.version_code = f'V{self.version_major}.{self.version_minor}'

    def make_version_snapshot(self):
        raise NotImplementedError

    @classmethod
    def get_key_fields(cls):
        return []


class EquipmentOperationStandard(VersionControlMixin):
    STAGE_STEAM = 'steam'
    STAGE_DRY = 'dry'
    STAGE_PREP = 'prep'
    STAGE_POST = 'post'

    STAGE_CHOICES = [
        (STAGE_PREP, '预处理阶段'),
        (STAGE_STEAM, '蒸制阶段'),
        (STAGE_DRY, '晾晒阶段'),
        (STAGE_POST, '后处理阶段'),
    ]

    SEVERITY_LOW = 'low'
    SEVERITY_MEDIUM = 'medium'
    SEVERITY_HIGH = 'high'
    SEVERITY_CRITICAL = 'critical'

    SEVERITY_CHOICES = [
        (SEVERITY_LOW, '一般'),
        (SEVERITY_MEDIUM, '重要'),
        (SEVERITY_HIGH, '关键'),
        (SEVERITY_CRITICAL, '致命'),
    ]

    equipment = models.ForeignKey(
        Equipment, on_delete=models.CASCADE,
        related_name='operation_standards', verbose_name='关联设备',
        blank=True, null=True
    )
    equipment_type = models.CharField(
        '设备类型', max_length=20,
        choices=Equipment.TYPE_CHOICES if hasattr(Equipment, 'TYPE_CHOICES') else [
            ('steamer', '蒸制设备'),
            ('drying_rack', '晾晒架'),
            ('other', '其他设备'),
        ],
        blank=True, null=True
    )
    herb_name = models.CharField('适用药材', max_length=100, blank=True, null=True)
    operation_stage = models.CharField('操作阶段', max_length=20, choices=STAGE_CHOICES)
    operation_name = models.CharField('操作项目名称', max_length=150)
    operation_steps = models.TextField('操作步骤说明')
    key_param_name = models.CharField('关键参数名称', max_length=100, blank=True, null=True)
    key_param_min = models.DecimalField('关键参数下限', max_digits=10, decimal_places=2, blank=True, null=True)
    key_param_max = models.DecimalField('关键参数上限', max_digits=10, decimal_places=2, blank=True, null=True)
    key_param_unit = models.CharField('参数单位', max_length=20, blank=True, null=True)
    param_severity = models.CharField(
        '参数严重等级', max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM
    )
    safety_requirements = models.TextField('安全注意事项', blank=True, null=True)
    quality_checkpoints = models.TextField('质量检查点', blank=True, null=True)
    tolerance_description = models.TextField('偏差容忍说明', blank=True, null=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '设备操作要求标准'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_operation_stage_display()}-{self.operation_name} ({self.version_code or "草稿"})'

    @classmethod
    def get_key_fields(cls):
        return [
            'operation_stage', 'operation_name', 'operation_steps',
            'key_param_name', 'key_param_min', 'key_param_max', 'key_param_unit',
            'param_severity', 'safety_requirements', 'quality_checkpoints',
        ]

    def make_version_snapshot(self):
        return {
            'equipment_id': self.equipment_id,
            'equipment_type': self.equipment_type,
            'herb_name': self.herb_name,
            'operation_stage': self.operation_stage,
            'operation_name': self.operation_name,
            'operation_steps': self.operation_steps,
            'key_param_name': self.key_param_name,
            'key_param_min': str(self.key_param_min) if self.key_param_min is not None else None,
            'key_param_max': str(self.key_param_max) if self.key_param_max is not None else None,
            'key_param_unit': self.key_param_unit,
            'param_severity': self.param_severity,
            'safety_requirements': self.safety_requirements,
            'quality_checkpoints': self.quality_checkpoints,
            'tolerance_description': self.tolerance_description,
        }

    def clean(self):
        errors = {}
        if not self.equipment_id and not self.equipment_type:
            errors['equipment'] = '关联设备和设备类型必须填写一项'
        if self.key_param_min is not None and self.key_param_max is not None:
            if self.key_param_min > self.key_param_max:
                errors['key_param_max'] = '参数上限不能小于下限'
        if errors:
            raise ValidationError(errors)


class AcceptanceRuleStandard(VersionControlMixin):
    RULE_TYPE_WEIGHT = 'weight_loss'
    RULE_TYPE_COLOR = 'color'
    RULE_TYPE_ABNORMAL = 'abnormal_count'
    RULE_TYPE_COMPREHENSIVE = 'comprehensive'
    RULE_TYPE_CUSTOM = 'custom'

    RULE_TYPE_CHOICES = [
        (RULE_TYPE_WEIGHT, '重量损耗规则'),
        (RULE_TYPE_COLOR, '色泽评级规则'),
        (RULE_TYPE_ABNORMAL, '异常次数规则'),
        (RULE_TYPE_COMPREHENSIVE, '综合评分规则'),
        (RULE_TYPE_CUSTOM, '自定义规则'),
    ]

    RESULT_PASS = 'pass'
    RESULT_FAIL = 'fail'
    RESULT_WARNING = 'warning'

    RESULT_CHOICES = [
        (RESULT_PASS, '合格'),
        (RESULT_WARNING, '警告'),
        (RESULT_FAIL, '不合格'),
    ]

    rule_name = models.CharField('规则名称', max_length=150)
    rule_type = models.CharField('规则类型', max_length=30, choices=RULE_TYPE_CHOICES)
    herb_name = models.CharField('适用药材', max_length=100, blank=True, null=True)
    template = models.ForeignKey(
        ProcessingStandardTemplate, on_delete=models.SET_NULL,
        related_name='acceptance_rules', verbose_name='关联炮制模板',
        blank=True, null=True
    )
    rule_description = models.TextField('规则描述')
    rule_condition = models.JSONField('规则条件', default=dict, blank=True)
    threshold_min = models.DecimalField('阈值下限', max_digits=10, decimal_places=2, blank=True, null=True)
    threshold_max = models.DecimalField('阈值上限', max_digits=10, decimal_places=2, blank=True, null=True)
    result_if_violated = models.CharField(
        '违反规则结论', max_length=20, choices=RESULT_CHOICES, default=RESULT_WARNING
    )
    weight_in_comprehensive = models.DecimalField(
        '综合评分权重(%)', max_digits=5, decimal_places=2, default=0
    )
    handling_advice = models.TextField('异常处理建议', blank=True, null=True)
    reference_standard = models.CharField('引用标准编号', max_length=100, blank=True, null=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '验收规则标准'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rule_name} ({self.version_code or "草稿"})'

    @classmethod
    def get_key_fields(cls):
        return [
            'rule_name', 'rule_type', 'rule_description', 'rule_condition',
            'threshold_min', 'threshold_max', 'result_if_violated',
            'weight_in_comprehensive', 'handling_advice',
        ]

    def make_version_snapshot(self):
        return {
            'rule_name': self.rule_name,
            'rule_type': self.rule_type,
            'herb_name': self.herb_name,
            'template_id': self.template_id,
            'rule_description': self.rule_description,
            'rule_condition': self.rule_condition,
            'threshold_min': str(self.threshold_min) if self.threshold_min is not None else None,
            'threshold_max': str(self.threshold_max) if self.threshold_max is not None else None,
            'result_if_violated': self.result_if_violated,
            'weight_in_comprehensive': str(self.weight_in_comprehensive),
            'handling_advice': self.handling_advice,
            'reference_standard': self.reference_standard,
        }

    def clean(self):
        errors = {}
        if self.threshold_min is not None and self.threshold_max is not None:
            if self.threshold_min > self.threshold_max:
                errors['threshold_max'] = '阈值上限不能小于下限'
        if self.weight_in_comprehensive < 0 or self.weight_in_comprehensive > 100:
            errors['weight_in_comprehensive'] = '权重必须在0-100之间'
        if errors:
            raise ValidationError(errors)

    def evaluate(self, batch):
        result = {
            'passed': True,
            'rule': str(self),
            'actual_value': None,
            'message': '',
        }
        try:
            assessment = getattr(batch, 'quality_assessment', None)
            rounds_qs = batch.rounds.all()

            if self.rule_type == self.RULE_TYPE_WEIGHT:
                value = assessment.total_weight_loss_percent if assessment else batch.get_weight_loss_percent()
                result['actual_value'] = float(value)
                result['message'] = f'重量损耗率: {value}%'
                if self.threshold_max is not None and float(value) > float(self.threshold_max):
                    result['passed'] = False
                    result['message'] += f' 超过上限 {self.threshold_max}%'
                if self.threshold_min is not None and float(value) < float(self.threshold_min):
                    result['passed'] = False
                    result['message'] += f' 低于下限 {self.threshold_min}%'

            elif self.rule_type == self.RULE_TYPE_COLOR:
                value = assessment.avg_color_score if assessment else 0
                result['actual_value'] = float(value)
                result['message'] = f'平均色泽评分: {value}'
                if self.threshold_min is not None and float(value) < float(self.threshold_min):
                    result['passed'] = False
                    result['message'] += f' 低于要求 {self.threshold_min}'

            elif self.rule_type == self.RULE_TYPE_ABNORMAL:
                value = assessment.abnormal_count if assessment else rounds_qs.filter(is_abnormal=True).count()
                result['actual_value'] = int(value)
                result['message'] = f'异常次数: {value}'
                if self.threshold_max is not None and int(value) > int(self.threshold_max):
                    result['passed'] = False
                    result['message'] += f' 超过允许值 {self.threshold_max}'

            elif self.rule_type == self.RULE_TYPE_COMPREHENSIVE:
                value = assessment.final_score if assessment else 0
                result['actual_value'] = float(value)
                result['message'] = f'综合评分: {value}'
                if self.threshold_min is not None and float(value) < float(self.threshold_min):
                    result['passed'] = False
                    result['message'] += f' 低于及格线 {self.threshold_min}'

        except Exception as e:
            result['passed'] = False
            result['message'] = f'评估出错: {e}'

        return result


STANDARD_TYPE_CHOICES = [
    ('processing_template', '炮制标准模板'),
    ('environment_standard', '环境参数标准'),
    ('equipment_operation', '设备操作要求'),
    ('acceptance_rule', '验收规则'),
]


class ChangeRequest(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SUBMITTED = 'submitted'
    STATUS_REVIEWING = 'reviewing'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUS_PUBLISHED = 'published'

    STATUS_CHOICES = [
        (STATUS_DRAFT, '草稿'),
        (STATUS_SUBMITTED, '已提交'),
        (STATUS_REVIEWING, '审核中'),
        (STATUS_APPROVED, '审核通过'),
        (STATUS_REJECTED, '已驳回'),
        (STATUS_CANCELLED, '已撤销'),
        (STATUS_PUBLISHED, '已发布'),
    ]

    CHANGE_TYPE_CREATE = 'create'
    CHANGE_TYPE_MODIFY = 'modify'
    CHANGE_TYPE_OBSOLETE = 'obsolete'

    CHANGE_TYPE_CHOICES = [
        (CHANGE_TYPE_CREATE, '新建标准'),
        (CHANGE_TYPE_MODIFY, '修改标准'),
        (CHANGE_TYPE_OBSOLETE, '废弃标准'),
    ]

    PRIORITY_LOW = 'low'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_HIGH = 'high'
    PRIORITY_URGENT = 'urgent'

    PRIORITY_CHOICES = [
        (PRIORITY_LOW, '低'),
        (PRIORITY_MEDIUM, '中'),
        (PRIORITY_HIGH, '高'),
        (PRIORITY_URGENT, '紧急'),
    ]

    request_no = models.CharField('变更申请编号', max_length=50, unique=True)
    standard_type = models.CharField('标准类型', max_length=30, choices=STANDARD_TYPE_CHOICES)
    change_type = models.CharField('变更类型', max_length=20, choices=CHANGE_TYPE_CHOICES)
    priority = models.CharField('优先级', max_length=20, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)

    source_standard_id = models.PositiveIntegerField('原标准ID', blank=True, null=True)
    source_version_code = models.CharField('原版本号', max_length=30, blank=True, null=True)
    target_standard_id = models.PositiveIntegerField('目标标准ID', blank=True, null=True)

    title = models.CharField('变更标题', max_length=200)
    change_reason = models.TextField('变更原因')
    impact_scope = models.TextField('影响范围')
    expected_effect = models.TextField('预期效果')
    risk_assessment = models.TextField('风险评估', blank=True, null=True)
    rollback_plan = models.TextField('回退方案', blank=True, null=True)

    change_content_before = models.JSONField('变更前内容快照', default=dict, blank=True)
    change_content_after = models.JSONField('变更后内容快照', default=dict, blank=True)
    changed_fields = models.JSONField('变更字段列表', default=list, blank=True)

    status = models.CharField('申请状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    current_reviewer = models.CharField('当前审核人', max_length=50, blank=True, null=True)

    applicant = models.CharField('申请人', max_length=50)
    department = models.CharField('申请部门', max_length=100, blank=True, null=True)
    requested_at = models.DateTimeField('申请时间', default=timezone.now)

    approved_at = models.DateTimeField('审核通过时间', blank=True, null=True)
    approver = models.CharField('审核人', max_length=50, blank=True, null=True)
    approval_remark = models.TextField('审核意见', blank=True, null=True)

    published_at = models.DateTimeField('发布时间', blank=True, null=True)
    publisher = models.CharField('发布人', max_length=50, blank=True, null=True)
    publish_remark = models.TextField('发布备注', blank=True, null=True)

    effective_date = models.DateField('生效日期', blank=True, null=True)
    obsolescence_date = models.DateField('旧版本废弃日期', blank=True, null=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '工艺变更申请'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_no} - {self.title}'

    def clean(self):
        if not self.request_no:
            self.request_no = self.generate_request_no()
        errors = {}
        if self.change_type != self.CHANGE_TYPE_CREATE and not self.source_standard_id:
            errors['source_standard_id'] = '修改/废弃标准必须指定原标准'
        if errors:
            raise ValidationError(errors)

    @classmethod
    def generate_request_no(cls):
        today = timezone.localdate()
        prefix = f'CR{today.strftime("%Y%m%d")}'
        count = cls.objects.filter(request_no__startswith=prefix).count()
        return f'{prefix}{count + 1:04d}'

    def save(self, *args, **kwargs):
        if not self.request_no:
            self.request_no = self.generate_request_no()
        super().save(*args, **kwargs)

    def add_approval_record(self, action, reviewer, remark=''):
        return ApprovalRecord.objects.create(
            change_request=self,
            action=action,
            reviewer=reviewer,
            remark=remark,
            reviewed_at=timezone.now(),
        )

    def get_standard_object(self, which='source'):
        std_id = self.source_standard_id if which == 'source' else self.target_standard_id
        if not std_id:
            return None
        model_map = {
            'processing_template': ProcessingStandardTemplate,
            'environment_standard': EnvironmentStandard,
            'equipment_operation': EquipmentOperationStandard,
            'acceptance_rule': AcceptanceRuleStandard,
        }
        model = model_map.get(self.standard_type)
        if not model:
            return None
        try:
            return model.objects.get(pk=std_id)
        except model.DoesNotExist:
            return None

    def compute_field_diffs(self):
        before = self.change_content_before or {}
        after = self.change_content_after or {}
        field_labels = {
            'template_name': '模板名称',
            'herb_name': '适用药材',
            'total_rounds': '总轮次数',
            'description': '模板说明',
            'steam_time_min': '蒸制时间下限',
            'steam_time_max': '蒸制时间上限',
            'dry_duration_min': '晾晒时长下限',
            'dry_duration_max': '晾晒时长上限',
            'weight_loss_max': '最大允许重量损耗',
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
            'weight_in_comprehensive': '综合评分权重',
            'handling_advice': '异常处理建议',
        }
        all_keys = set(list(before.keys()) + list(after.keys()))
        diffs = []
        for key in all_keys:
            b = before.get(key)
            a = after.get(key)
            if b != a:
                diffs.append({
                    'field': key,
                    'field_label': field_labels.get(key, key),
                    'before': b,
                    'after': a,
                })
        self.changed_fields = diffs
        return diffs


class ApprovalRecord(models.Model):
    ACTION_SUBMIT = 'submit'
    ACTION_REVIEW_START = 'review_start'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_CANCEL = 'cancel'
    ACTION_PUBLISH = 'publish'
    ACTION_REVISE = 'revise'
    ACTION_COMMENT = 'comment'

    ACTION_CHOICES = [
        (ACTION_SUBMIT, '提交申请'),
        (ACTION_REVIEW_START, '开始审核'),
        (ACTION_APPROVE, '审核通过'),
        (ACTION_REJECT, '审核驳回'),
        (ACTION_CANCEL, '撤销申请'),
        (ACTION_PUBLISH, '发布版本'),
        (ACTION_REVISE, '修改重提'),
        (ACTION_COMMENT, '添加备注'),
    ]

    change_request = models.ForeignKey(
        ChangeRequest, on_delete=models.CASCADE,
        related_name='approval_records', verbose_name='变更申请'
    )
    action = models.CharField('操作动作', max_length=20, choices=ACTION_CHOICES)
    reviewer = models.CharField('操作人', max_length=50)
    remark = models.TextField('操作意见/备注', blank=True, null=True)
    reviewed_at = models.DateTimeField('操作时间', default=timezone.now)
    previous_status = models.CharField('操作前状态', max_length=20, blank=True, null=True)
    new_status = models.CharField('操作后状态', max_length=20, blank=True, null=True)

    class Meta:
        verbose_name = '审核操作记录'
        verbose_name_plural = verbose_name
        ordering = ['change_request', 'reviewed_at']

    def __str__(self):
        return f'{self.change_request.request_no} - {self.get_action_display()} by {self.reviewer}'


class ProcessVersionSnapshot(models.Model):
    snapshot_name = models.CharField('快照名称', max_length=200)
    snapshot_no = models.CharField('快照编号', max_length=50, unique=True)
    description = models.TextField('快照说明', blank=True, null=True)

    template_id = models.PositiveIntegerField('炮制标准模板ID', blank=True, null=True)
    template_version = models.CharField('模板版本号', max_length=30, blank=True, null=True)
    template_snapshot = models.JSONField('模板内容快照', default=dict, blank=True)
    round_standards_snapshot = models.JSONField('轮次标准快照', default=list, blank=True)

    env_standard_ids = models.JSONField('环境标准ID列表', default=list, blank=True)
    env_standards_snapshot = models.JSONField('环境标准快照', default=list, blank=True)

    equipment_op_ids = models.JSONField('设备操作要求ID列表', default=list, blank=True)
    equipment_op_snapshot = models.JSONField('设备操作要求快照', default=list, blank=True)

    acceptance_rule_ids = models.JSONField('验收规则ID列表', default=list, blank=True)
    acceptance_rules_snapshot = models.JSONField('验收规则快照', default=list, blank=True)

    related_change_request_id = models.PositiveIntegerField('关联变更申请ID', blank=True, null=True)
    is_active = models.BooleanField('是否启用', default=True)

    created_by = models.CharField('创建人', max_length=50, blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '工艺版本快照'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.snapshot_no} - {self.snapshot_name}'

    @classmethod
    def generate_snapshot_no(cls):
        today = timezone.localdate()
        prefix = f'PVS{today.strftime("%Y%m%d")}'
        count = cls.objects.filter(snapshot_no__startswith=prefix).count()
        return f'{prefix}{count + 1:04d}'

    def save(self, *args, **kwargs):
        if not self.snapshot_no:
            self.snapshot_no = self.generate_snapshot_no()
        super().save(*args, **kwargs)

    @classmethod
    def create_from_template(cls, template, name='', user=''):
        if not template:
            return None
        if not name:
            name = f'{template.template_name} - 版本快照'
        round_standards = []
        for rs in template.round_standards.all():
            round_standards.append({
                'round_no': rs.round_no,
                'steam_time_min': str(rs.steam_time_min),
                'steam_time_max': str(rs.steam_time_max),
                'dry_duration_min': str(rs.dry_duration_min),
                'dry_duration_max': str(rs.dry_duration_max),
                'weight_loss_max': str(rs.weight_loss_max),
                'required_color': rs.required_color,
            })
        template_version = getattr(template, 'version_code', '')
        return cls.objects.create(
            snapshot_name=name,
            template_id=template.pk,
            template_version=template_version,
            template_snapshot={
                'template_name': template.template_name,
                'herb_name': template.herb_name,
                'total_rounds': template.total_rounds,
                'description': template.description,
            },
            round_standards_snapshot=round_standards,
            created_by=user,
        )


class BatchProcessVersionLink(models.Model):
    batch = models.OneToOneField(
        HerbBatch, on_delete=models.CASCADE,
        related_name='process_version_link', verbose_name='批次'
    )
    version_snapshot = models.ForeignKey(
        ProcessVersionSnapshot, on_delete=models.SET_NULL,
        related_name='batch_links', verbose_name='工艺版本快照',
        blank=True, null=True
    )
    template_id_at_use = models.PositiveIntegerField('使用时模板ID', blank=True, null=True)
    template_version_at_use = models.CharField('使用时模板版本', max_length=30, blank=True, null=True)
    template_snapshot_at_use = models.JSONField('使用时模板快照', default=dict, blank=True)
    round_standards_at_use = models.JSONField('使用时轮次标准快照', default=list, blank=True)
    env_standards_at_use = models.JSONField('使用时环境标准快照', default=list, blank=True)
    equipment_ops_at_use = models.JSONField('使用时设备操作快照', default=list, blank=True)
    acceptance_rules_at_use = models.JSONField('使用时验收规则快照', default=list, blank=True)

    linked_at = models.DateTimeField('关联时间', default=timezone.now)
    linked_by = models.CharField('关联操作人', max_length=50, blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)

    class Meta:
        verbose_name = '批次工艺版本关联'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.batch.batch_no} - {self.template_version_at_use or "未关联版本"}'

    @classmethod
    def link_batch_to_current(cls, batch, user='', snapshot=None):
        template = batch.template
        link, _ = cls.objects.get_or_create(batch=batch)
        if snapshot:
            link.version_snapshot = snapshot
        if template:
            link.template_id_at_use = template.pk
            link.template_version_at_use = getattr(template, 'version_code', '')
            link.template_snapshot_at_use = {
                'template_name': template.template_name,
                'herb_name': template.herb_name,
                'total_rounds': template.total_rounds,
                'description': template.description,
            }
            round_standards = []
            for rs in template.round_standards.all():
                round_standards.append({
                    'round_no': rs.round_no,
                    'steam_time_min': str(rs.steam_time_min),
                    'steam_time_max': str(rs.steam_time_max),
                    'dry_duration_min': str(rs.dry_duration_min),
                    'dry_duration_max': str(rs.dry_duration_max),
                    'weight_loss_max': str(rs.weight_loss_max),
                    'required_color': rs.required_color,
                })
            link.round_standards_at_use = round_standards

            env_standards = []
            for es in EnvironmentStandard.objects.filter(
                herb_name=template.herb_name, is_active=True
            ):
                env_standards.append({
                    'id': es.pk,
                    'version': getattr(es, 'version_code', ''),
                    'param_type': es.param_type,
                    'stage': es.stage,
                    'min_value': str(es.min_value),
                    'max_value': str(es.max_value),
                    'unit': es.unit,
                    'description': es.description,
                })
            link.env_standards_at_use = env_standards

            equip_ops = []
            for eo in EquipmentOperationStandard.objects.filter(
                herb_name=template.herb_name,
                version_status=EquipmentOperationStandard.VERSION_STATUS_APPROVED,
                is_current=True,
            ):
                equip_ops.append({
                    'id': eo.pk,
                    'version': eo.version_code,
                    'operation_stage': eo.operation_stage,
                    'operation_name': eo.operation_name,
                    'key_param_name': eo.key_param_name,
                    'key_param_min': str(eo.key_param_min) if eo.key_param_min else None,
                    'key_param_max': str(eo.key_param_max) if eo.key_param_max else None,
                    'key_param_unit': eo.key_param_unit,
                })
            link.equipment_ops_at_use = equip_ops

            acc_rules = []
            for ar in AcceptanceRuleStandard.objects.filter(
                template_id=template.pk,
                version_status=AcceptanceRuleStandard.VERSION_STATUS_APPROVED,
                is_current=True,
            ) | AcceptanceRuleStandard.objects.filter(
                herb_name=template.herb_name,
                version_status=AcceptanceRuleStandard.VERSION_STATUS_APPROVED,
                is_current=True,
            ):
                acc_rules.append({
                    'id': ar.pk,
                    'version': ar.version_code,
                    'rule_name': ar.rule_name,
                    'rule_type': ar.rule_type,
                    'threshold_min': str(ar.threshold_min) if ar.threshold_min else None,
                    'threshold_max': str(ar.threshold_max) if ar.threshold_max else None,
                    'result_if_violated': ar.result_if_violated,
                })
            link.acceptance_rules_at_use = acc_rules

        link.linked_by = user
        link.save()
        return link


class QualityFluctuationAnalysis(models.Model):
    ANALYSIS_STATUS_PENDING = 'pending'
    ANALYSIS_STATUS_COMPLETED = 'completed'
    ANALYSIS_STATUS_REVIEWED = 'reviewed'

    STATUS_CHOICES = [
        (ANALYSIS_STATUS_PENDING, '待分析'),
        (ANALYSIS_STATUS_COMPLETED, '分析完成'),
        (ANALYSIS_STATUS_REVIEWED, '已复核'),
    ]

    TREND_IMPROVED = 'improved'
    TREND_STABLE = 'stable'
    TREND_DECLINED = 'declined'
    TREND_INCONCLUSIVE = 'inconclusive'

    TREND_CHOICES = [
        (TREND_IMPROVED, '改善'),
        (TREND_STABLE, '稳定'),
        (TREND_DECLINED, '下降'),
        (TREND_INCONCLUSIVE, '无法判断'),
    ]

    analysis_no = models.CharField('分析编号', max_length=50, unique=True)
    title = models.CharField('分析标题', max_length=200)
    related_change_request = models.ForeignKey(
        ChangeRequest, on_delete=models.SET_NULL,
        related_name='quality_analyses', verbose_name='关联变更申请',
        blank=True, null=True
    )
    standard_type = models.CharField(
        '标准类型', max_length=30, choices=STANDARD_TYPE_CHOICES, blank=True, null=True
    )
    standard_id = models.PositiveIntegerField('标准ID', blank=True, null=True)
    herb_name = models.CharField('适用药材', max_length=100, blank=True, null=True)

    before_version = models.CharField('变更前版本号', max_length=30, blank=True, null=True)
    after_version = models.CharField('变更后版本号', max_length=30, blank=True, null=True)
    before_start_date = models.DateField('变更前统计起始日期', blank=True, null=True)
    before_end_date = models.DateField('变更前统计截止日期', blank=True, null=True)
    after_start_date = models.DateField('变更后统计起始日期', blank=True, null=True)
    after_end_date = models.DateField('变更后统计截止日期', blank=True, null=True)

    before_batch_count = models.PositiveIntegerField('变更前批次数量', default=0)
    after_batch_count = models.PositiveIntegerField('变更后批次数量', default=0)

    before_avg_score = models.DecimalField(
        '变更前平均综合评分', max_digits=5, decimal_places=2, blank=True, null=True
    )
    after_avg_score = models.DecimalField(
        '变更后平均综合评分', max_digits=5, decimal_places=2, blank=True, null=True
    )
    score_change_pct = models.DecimalField(
        '评分变化率(%)', max_digits=6, decimal_places=2, blank=True, null=True
    )

    before_pass_rate = models.DecimalField(
        '变更前合格率(%)', max_digits=5, decimal_places=2, blank=True, null=True
    )
    after_pass_rate = models.DecimalField(
        '变更后合格率(%)', max_digits=5, decimal_places=2, blank=True, null=True
    )
    pass_rate_change = models.DecimalField(
        '合格率变化(%)', max_digits=6, decimal_places=2, blank=True, null=True
    )

    before_avg_weight_loss = models.DecimalField(
        '变更前平均重量损耗(%)', max_digits=5, decimal_places=2, blank=True, null=True
    )
    after_avg_weight_loss = models.DecimalField(
        '变更后平均重量损耗(%)', max_digits=5, decimal_places=2, blank=True, null=True
    )
    weight_loss_change = models.DecimalField(
        '损耗变化(%)', max_digits=6, decimal_places=2, blank=True, null=True
    )

    before_avg_color_score = models.DecimalField(
        '变更前平均色泽评分', max_digits=5, decimal_places=2, blank=True, null=True
    )
    after_avg_color_score = models.DecimalField(
        '变更后平均色泽评分', max_digits=5, decimal_places=2, blank=True, null=True
    )
    color_score_change = models.DecimalField(
        '色泽评分变化', max_digits=6, decimal_places=2, blank=True, null=True
    )

    before_abnormal_rate = models.DecimalField(
        '变更前异常率(%)', max_digits=5, decimal_places=2, blank=True, null=True
    )
    after_abnormal_rate = models.DecimalField(
        '变更后异常率(%)', max_digits=5, decimal_places=2, blank=True, null=True
    )
    abnormal_rate_change = models.DecimalField(
        '异常率变化(%)', max_digits=6, decimal_places=2, blank=True, null=True
    )

    score_std_dev_before = models.DecimalField(
        '变更前评分标准差', max_digits=6, decimal_places=2, blank=True, null=True
    )
    score_std_dev_after = models.DecimalField(
        '变更后评分标准差', max_digits=6, decimal_places=2, blank=True, null=True
    )
    stability_change = models.CharField(
        '稳定性变化趋势', max_length=20, choices=TREND_CHOICES, default=TREND_INCONCLUSIVE
    )
    overall_trend = models.CharField(
        '总体质量趋势', max_length=20, choices=TREND_CHOICES, default=TREND_INCONCLUSIVE
    )

    before_batch_ids = models.JSONField('变更前批次ID列表', default=list, blank=True)
    after_batch_ids = models.JSONField('变更后批次ID列表', default=list, blank=True)
    detailed_comparison = models.JSONField('详细对比数据', default=dict, blank=True)

    analysis_conclusion = models.TextField('分析结论', blank=True, null=True)
    improvement_suggestions = models.TextField('改进建议', blank=True, null=True)
    statistical_notes = models.TextField('统计说明', blank=True, null=True)

    status = models.CharField('分析状态', max_length=20, choices=STATUS_CHOICES, default=ANALYSIS_STATUS_PENDING)
    analyzed_by = models.CharField('分析人', max_length=50, blank=True, null=True)
    analyzed_at = models.DateTimeField('分析时间', blank=True, null=True)
    reviewed_by = models.CharField('复核人', max_length=50, blank=True, null=True)
    reviewed_at = models.DateTimeField('复核时间', blank=True, null=True)
    review_remark = models.TextField('复核意见', blank=True, null=True)

    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '工艺变更质量波动分析'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.analysis_no} - {self.title}'

    @classmethod
    def generate_analysis_no(cls):
        today = timezone.localdate()
        prefix = f'QFA{today.strftime("%Y%m%d")}'
        count = cls.objects.filter(analysis_no__startswith=prefix).count()
        return f'{prefix}{count + 1:04d}'

    def save(self, *args, **kwargs):
        if not self.analysis_no:
            self.analysis_no = self.generate_analysis_no()
        super().save(*args, **kwargs)

    def _stat(self, values):
        if not values:
            return None, None, None
        n = len(values)
        avg = sum(values) / n
        if n > 1:
            variance = sum((v - avg) ** 2 for v in values) / (n - 1)
            std_dev = variance ** 0.5
        else:
            std_dev = 0.0
        return round(avg, 2), round(std_dev, 2), n

    def _get_assessment_data(self, batches):
        data = {
            'scores': [],
            'weight_losses': [],
            'color_scores': [],
            'abnormal_counts': [],
            'pass_count': 0,
            'batch_ids': [],
        }
        from herbapp.models import BatchQualityAssessment, Acceptance
        for batch in batches:
            data['batch_ids'].append(batch.pk)
            try:
                assess = batch.quality_assessment
                data['scores'].append(float(assess.final_score))
                data['weight_losses'].append(float(assess.total_weight_loss_percent))
                data['color_scores'].append(float(assess.avg_color_score))
                data['abnormal_counts'].append(int(assess.abnormal_count))
            except Exception:
                loss = batch.get_weight_loss_percent()
                data['weight_losses'].append(float(loss))
            try:
                acc = batch.acceptance
                if acc.result == Acceptance.RESULT_PASS:
                    data['pass_count'] += 1
            except Exception:
                pass
        return data

    def run_analysis(self):
        herb_filter = models.Q()
        if self.herb_name:
            herb_filter = models.Q(herb_name=self.herb_name)

        before_batches = HerbBatch.objects.filter(
            herb_filter,
            status__in=[HerbBatch.STATUS_COMPLETED, HerbBatch.STATUS_ACCEPTED],
        )
        after_batches = HerbBatch.objects.filter(
            herb_filter,
            status__in=[HerbBatch.STATUS_COMPLETED, HerbBatch.STATUS_ACCEPTED],
        )

        if self.before_start_date:
            before_batches = before_batches.filter(created_at__date__gte=self.before_start_date)
        if self.before_end_date:
            before_batches = before_batches.filter(created_at__date__lte=self.before_end_date)
        if self.after_start_date:
            after_batches = after_batches.filter(created_at__date__gte=self.after_start_date)
        if self.after_end_date:
            after_batches = after_batches.filter(created_at__date__lte=self.after_end_date)

        before_data = self._get_assessment_data(before_batches)
        after_data = self._get_assessment_data(after_batches)

        self.before_batch_count = len(before_data['batch_ids'])
        self.after_batch_count = len(after_data['batch_ids'])
        self.before_batch_ids = before_data['batch_ids']
        self.after_batch_ids = after_data['batch_ids']

        before_avg, before_std, _ = self._stat(before_data['scores'])
        after_avg, after_std, _ = self._stat(after_data['scores'])
        if before_avg is not None:
            self.before_avg_score = before_avg
            self.score_std_dev_before = before_std
        if after_avg is not None:
            self.after_avg_score = after_avg
            self.score_std_dev_after = after_std
        if before_avg and after_avg and before_avg > 0:
            self.score_change_pct = round((after_avg - before_avg) / before_avg * 100, 2)

        if self.before_batch_count:
            self.before_pass_rate = round(before_data['pass_count'] / self.before_batch_count * 100, 2)
        if self.after_batch_count:
            self.after_pass_rate = round(after_data['pass_count'] / self.after_batch_count * 100, 2)
        if self.before_pass_rate is not None and self.after_pass_rate is not None:
            self.pass_rate_change = round(self.after_pass_rate - self.before_pass_rate, 2)

        b_loss_avg, _, _ = self._stat(before_data['weight_losses'])
        a_loss_avg, _, _ = self._stat(after_data['weight_losses'])
        if b_loss_avg is not None:
            self.before_avg_weight_loss = b_loss_avg
        if a_loss_avg is not None:
            self.after_avg_weight_loss = a_loss_avg
        if b_loss_avg is not None and a_loss_avg is not None:
            self.weight_loss_change = round(a_loss_avg - b_loss_avg, 2)

        b_color_avg, _, _ = self._stat(before_data['color_scores'])
        a_color_avg, _, _ = self._stat(after_data['color_scores'])
        if b_color_avg is not None:
            self.before_avg_color_score = b_color_avg
        if a_color_avg is not None:
            self.after_avg_color_score = a_color_avg
        if b_color_avg is not None and a_color_avg is not None:
            self.color_score_change = round(a_color_avg - b_color_avg, 2)

        if before_data['abnormal_counts']:
            total_rounds_before = sum(before_data['abnormal_counts'])
            total_possible_before = max(1, sum(
                b.required_rounds for b in before_batches.filter(pk__in=before_data['batch_ids'])
            ))
            self.before_abnormal_rate = round(total_rounds_before / total_possible_before * 100, 2)
        if after_data['abnormal_counts']:
            total_rounds_after = sum(after_data['abnormal_counts'])
            total_possible_after = max(1, sum(
                b.required_rounds for b in after_batches.filter(pk__in=after_data['batch_ids'])
            ))
            self.after_abnormal_rate = round(total_rounds_after / total_possible_after * 100, 2)
        if self.before_abnormal_rate is not None and self.after_abnormal_rate is not None:
            self.abnormal_rate_change = round(self.after_abnormal_rate - self.before_abnormal_rate, 2)

        if before_std is not None and after_std is not None:
            if after_std < before_std - 1:
                self.stability_change = self.TREND_IMPROVED
            elif after_std > before_std + 1:
                self.stability_change = self.TREND_DECLINED
            else:
                self.stability_change = self.TREND_STABLE

        score_trend = 0
        if self.score_change_pct is not None:
            if self.score_change_pct >= 3:
                score_trend = 2
            elif self.score_change_pct <= -3:
                score_trend = -2

        pass_trend = 0
        if self.pass_rate_change is not None:
            if self.pass_rate_change >= 5:
                pass_trend = 2
            elif self.pass_rate_change <= -5:
                pass_trend = -2

        if score_trend + pass_trend >= 2:
            self.overall_trend = self.TREND_IMPROVED
        elif score_trend + pass_trend <= -2:
            self.overall_trend = self.TREND_DECLINED
        elif self.stability_change == self.TREND_IMPROVED:
            self.overall_trend = self.TREND_IMPROVED
        elif self.stability_change == self.TREND_DECLINED:
            self.overall_trend = self.TREND_DECLINED
        else:
            self.overall_trend = self.TREND_STABLE

        self.detailed_comparison = {
            'before': {
                'scores': before_data['scores'],
                'weight_losses': before_data['weight_losses'],
                'color_scores': before_data['color_scores'],
                'abnormal_counts': before_data['abnormal_counts'],
            },
            'after': {
                'scores': after_data['scores'],
                'weight_losses': after_data['weight_losses'],
                'color_scores': after_data['color_scores'],
                'abnormal_counts': after_data['abnormal_counts'],
            },
        }

        self.analyzed_at = timezone.now()
        self.status = self.ANALYSIS_STATUS_COMPLETED
        self.save()
        return True
