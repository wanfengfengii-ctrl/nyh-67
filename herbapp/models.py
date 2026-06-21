from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ProcessingStandardTemplate(models.Model):
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

    template_name = models.CharField('模板名称', max_length=100)
    herb_name = models.CharField('适用药材', max_length=100)
    total_rounds = models.PositiveIntegerField('总轮次数', default=9)
    description = models.TextField('模板说明', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    is_active = models.BooleanField('是否启用', default=True)

    version_code = models.CharField('版本号', max_length=30, blank=True, null=True)
    version_major = models.PositiveIntegerField('主版本号', default=1)
    version_minor = models.PositiveIntegerField('次版本号', default=0)
    version_status = models.CharField(
        '版本状态', max_length=20, choices=VERSION_STATUS_CHOICES,
        default=VERSION_STATUS_APPROVED
    )
    master_id = models.PositiveIntegerField('主记录ID', blank=True, null=True)
    is_current = models.BooleanField('是否当前版本', default=True)
    version_remark = models.TextField('版本说明', blank=True, null=True)
    version_created_at = models.DateTimeField('版本创建时间', blank=True, null=True)
    version_created_by = models.CharField('版本创建人', max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = '炮制标准模板'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        version = f' [{self.version_code}]' if self.version_code else ''
        return f'{self.template_name}{version} ({self.herb_name} - {self.total_rounds}轮)'

    def clean(self):
        if self.total_rounds is not None and self.total_rounds < 1:
            raise ValidationError({'total_rounds': '总轮次必须大于等于1'})
        if not self.version_code:
            self.version_code = f'V{self.version_major}.{self.version_minor}'

    def save(self, *args, **kwargs):
        if not self.version_code:
            self.version_code = f'V{self.version_major}.{self.version_minor}'
        if not self.version_created_at:
            self.version_created_at = self.created_at or timezone.now()
        super().save(*args, **kwargs)

    @classmethod
    def get_key_fields(cls):
        return [
            'template_name', 'herb_name', 'total_rounds', 'description',
        ]

    def make_version_snapshot(self, include_rounds=True):
        snap = {
            'template_name': self.template_name,
            'herb_name': self.herb_name,
            'total_rounds': self.total_rounds,
            'description': self.description,
            'version_code': self.version_code,
            'version_major': self.version_major,
            'version_minor': self.version_minor,
        }
        if include_rounds:
            rounds_snap = []
            for rs in self.round_standards.all():
                rounds_snap.append({
                    'round_no': rs.round_no,
                    'steam_time_min': str(rs.steam_time_min),
                    'steam_time_max': str(rs.steam_time_max),
                    'dry_duration_min': str(rs.dry_duration_min),
                    'dry_duration_max': str(rs.dry_duration_max),
                    'weight_loss_max': str(rs.weight_loss_max),
                    'required_color': rs.required_color,
                })
            snap['round_standards'] = rounds_snap
        return snap


class RoundStandard(models.Model):
    template = models.ForeignKey(
        ProcessingStandardTemplate, on_delete=models.CASCADE, related_name='round_standards', verbose_name='所属模板'
    )
    round_no = models.PositiveIntegerField('轮次序号')
    steam_time_min = models.DecimalField('蒸制时间下限(分钟)', max_digits=6, decimal_places=1)
    steam_time_max = models.DecimalField('蒸制时间上限(分钟)', max_digits=6, decimal_places=1)
    dry_duration_min = models.DecimalField('晾晒时长下限(小时)', max_digits=6, decimal_places=1)
    dry_duration_max = models.DecimalField('晾晒时长上限(小时)', max_digits=6, decimal_places=1)
    weight_loss_max = models.DecimalField('最大允许重量损耗(%)', max_digits=5, decimal_places=2, default=15.00)
    required_color = models.CharField(
        '色泽要求', max_length=20,
        choices=[
            ('excellent', '优'),
            ('good', '良以上'),
            ('normal', '中以上'),
        ],
        default='good'
    )

    class Meta:
        verbose_name = '轮次标准'
        verbose_name_plural = verbose_name
        ordering = ['template', 'round_no']
        unique_together = [('template', 'round_no')]

    def __str__(self):
        return f'{self.template.template_name} - 第{self.round_no}轮'

    def clean(self):
        errors = {}
        if self.steam_time_min is not None and self.steam_time_max is not None:
            if self.steam_time_min <= 0:
                errors['steam_time_min'] = '蒸制时间下限必须大于0'
            if self.steam_time_max <= 0:
                errors['steam_time_max'] = '蒸制时间上限必须大于0'
            if self.steam_time_min > self.steam_time_max:
                errors['steam_time_max'] = '蒸制时间上限不能小于下限'
        if self.dry_duration_min is not None and self.dry_duration_max is not None:
            if self.dry_duration_min <= 0:
                errors['dry_duration_min'] = '晾晒时长下限必须大于0'
            if self.dry_duration_max <= 0:
                errors['dry_duration_max'] = '晾晒时长上限必须大于0'
            if self.dry_duration_min > self.dry_duration_max:
                errors['dry_duration_max'] = '晾晒时长上限不能小于下限'
        if self.weight_loss_max is not None:
            if self.weight_loss_max < 0:
                errors['weight_loss_max'] = '最大允许损耗不能为负数'
            if self.weight_loss_max > 100:
                errors['weight_loss_max'] = '最大允许损耗不能超过100%'
        if errors:
            raise ValidationError(errors)


class HerbBatch(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_ACCEPTED = 'accepted'

    STATUS_CHOICES = [
        (STATUS_PENDING, '待炮制'),
        (STATUS_PROCESSING, '炮制中'),
        (STATUS_COMPLETED, '待验收'),
        (STATUS_ACCEPTED, '已验收'),
    ]

    template = models.ForeignKey(
        ProcessingStandardTemplate, on_delete=models.SET_NULL,
        related_name='batches', verbose_name='引用标准模板',
        blank=True, null=True
    )
    batch_no = models.CharField('批次编号', max_length=50, unique=True)
    herb_name = models.CharField('药材名称', max_length=100)
    initial_weight = models.DecimalField('初始重量(g)', max_digits=10, decimal_places=2)
    required_rounds = models.PositiveIntegerField('规定轮次', default=9)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    remark = models.TextField('备注', blank=True, null=True)

    class Meta:
        verbose_name = '药材批次'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.batch_no} - {self.herb_name}'

    def clean(self):
        if self.initial_weight is not None and self.initial_weight <= 0:
            raise ValidationError({'initial_weight': '初始重量必须大于0'})
        if self.required_rounds is not None and self.required_rounds < 1:
            raise ValidationError({'required_rounds': '规定轮次必须大于等于1'})

    def get_current_round_no(self):
        return self.rounds.count()

    def get_next_round_no(self):
        return self.get_current_round_no() + 1

    def can_add_round(self):
        return self.get_current_round_no() < self.required_rounds and self.status != self.STATUS_ACCEPTED

    def can_accept(self):
        return self.get_current_round_no() >= self.required_rounds and self.status == self.STATUS_COMPLETED

    def update_status(self):
        current = self.get_current_round_no()
        if current == 0:
            self.status = self.STATUS_PENDING
        elif current < self.required_rounds:
            self.status = self.STATUS_PROCESSING
        else:
            self.status = self.STATUS_COMPLETED
        self.save()

    def get_weight_loss_percent(self):
        last_round = self.rounds.order_by('-round_no').first()
        if not last_round:
            return 0
        loss = (self.initial_weight - last_round.weight) / self.initial_weight * 100
        return round(float(loss), 2)


class ProcessingRound(models.Model):
    COLOR_EXCELLENT = 'excellent'
    COLOR_GOOD = 'good'
    COLOR_NORMAL = 'normal'
    COLOR_ABNORMAL = 'abnormal'

    COLOR_CHOICES = [
        (COLOR_EXCELLENT, '优'),
        (COLOR_GOOD, '良'),
        (COLOR_NORMAL, '中'),
        (COLOR_ABNORMAL, '异常'),
    ]

    REVIEW_PASS = 'pass'
    REVIEW_REJECT = 'reject'
    REVIEW_PENDING = 'pending'

    REVIEW_CHOICES = [
        (REVIEW_PENDING, '待复核'),
        (REVIEW_PASS, '通过'),
        (REVIEW_REJECT, '驳回'),
    ]

    batch = models.ForeignKey(
        HerbBatch, on_delete=models.CASCADE, related_name='rounds', verbose_name='所属批次'
    )
    round_no = models.PositiveIntegerField('轮次序号')
    steam_time = models.DecimalField('蒸制时间(分钟)', max_digits=6, decimal_places=1)
    dry_duration = models.DecimalField('晾晒时长(小时)', max_digits=6, decimal_places=1)
    weight = models.DecimalField('当前重量(g)', max_digits=10, decimal_places=2)
    color_rating = models.CharField('色泽评级', max_length=20, choices=COLOR_CHOICES)
    is_abnormal = models.BooleanField('是否异常', default=False)
    abnormal_reasons = models.JSONField('异常原因详情', default=dict, blank=True)
    handling_opinion = models.TextField('处理意见', blank=True, null=True)
    review_status = models.CharField('复核状态', max_length=20, choices=REVIEW_CHOICES, default=REVIEW_PENDING)
    review_result = models.TextField('复核结果', blank=True, null=True)
    reviewer = models.CharField('复核人', max_length=50, blank=True, null=True)
    reviewed_at = models.DateTimeField('复核时间', blank=True, null=True)
    record_time = models.DateTimeField('记录时间', auto_now_add=True)

    class Meta:
        verbose_name = '炮制轮次'
        verbose_name_plural = verbose_name
        ordering = ['batch', 'round_no']
        unique_together = [('batch', 'round_no')]

    def __str__(self):
        return f'{self.batch.batch_no} - 第{self.round_no}轮'

    def get_weight_loss_percent(self):
        if not self.batch_id:
            return 0
        loss = (self.batch.initial_weight - self.weight) / self.batch.initial_weight * 100
        return round(float(loss), 2)

    def detect_abnormalities(self):
        reasons = {}
        is_abnormal = False

        if self.batch_id and self.batch.template_id:
            standard = self.batch.template.round_standards.filter(round_no=self.round_no).first()
            if standard:
                if self.steam_time < standard.steam_time_min:
                    reasons['steam_time'] = f'蒸制时间{self.steam_time}分钟低于标准下限{standard.steam_time_min}分钟'
                    is_abnormal = True
                if self.steam_time > standard.steam_time_max:
                    reasons['steam_time'] = f'蒸制时间{self.steam_time}分钟超出标准上限{standard.steam_time_max}分钟'
                    is_abnormal = True

                if self.dry_duration < standard.dry_duration_min:
                    reasons['dry_duration'] = f'晾晒时长{self.dry_duration}小时低于标准下限{standard.dry_duration_min}小时'
                    is_abnormal = True
                if self.dry_duration > standard.dry_duration_max:
                    reasons['dry_duration'] = f'晾晒时长{self.dry_duration}小时超出标准上限{standard.dry_duration_max}小时'
                    is_abnormal = True

                loss_pct = self.get_weight_loss_percent()
                if loss_pct > float(standard.weight_loss_max):
                    reasons['weight_loss'] = f'重量损耗{loss_pct}%超出最大允许值{standard.weight_loss_max}%'
                    is_abnormal = True

                color_rank = {'excellent': 3, 'good': 2, 'normal': 1, 'abnormal': 0}
                required_rank = {'excellent': 3, 'good': 2, 'normal': 1}
                if color_rank.get(self.color_rating, 0) < required_rank.get(standard.required_color, 0):
                    reasons['color'] = f'色泽评级{self.get_color_rating_display()}未达到要求的{standard.get_required_color_display()}'
                    is_abnormal = True

        if self.color_rating == self.COLOR_ABNORMAL:
            reasons['color_abnormal'] = '色泽评级为异常'
            is_abnormal = True

        self.is_abnormal = is_abnormal
        self.abnormal_reasons = reasons
        return is_abnormal, reasons

    def clean(self):
        errors = {}
        if self.steam_time is not None and self.steam_time <= 0:
            errors['steam_time'] = '蒸制时间必须大于0'
        if self.dry_duration is not None and self.dry_duration <= 0:
            errors['dry_duration'] = '晾晒时长必须大于0'
        if self.weight is not None:
            if self.weight <= 0:
                errors['weight'] = '当前重量必须大于0'
            if self.batch_id and self.weight > self.batch.initial_weight:
                errors['weight'] = '当前重量不能大于初始重量'

        is_abnormal, reasons = self.detect_abnormalities()
        if is_abnormal and not self.handling_opinion:
            errors['handling_opinion'] = '检测到数据异常，必须填写处理意见'

        if errors:
            raise ValidationError(errors)


class Acceptance(models.Model):
    RESULT_PASS = 'pass'
    RESULT_FAIL = 'fail'
    RESULT_REPROCESS = 'reprocess'

    RESULT_CHOICES = [
        (RESULT_PASS, '合格'),
        (RESULT_FAIL, '不合格'),
        (RESULT_REPROCESS, '返工'),
    ]

    batch = models.OneToOneField(
        HerbBatch, on_delete=models.CASCADE, related_name='acceptance', verbose_name='所属批次'
    )
    result = models.CharField('验收结果', max_length=20, choices=RESULT_CHOICES)
    remark = models.TextField('验收备注')
    accepted_at = models.DateTimeField('验收时间', auto_now_add=True)

    class Meta:
        verbose_name = '质量验收'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.batch.batch_no} - {self.get_result_display()}'


class BatchQualityAssessment(models.Model):
    GRADE_EXCELLENT = 'excellent'
    GRADE_GOOD = 'good'
    GRADE_NORMAL = 'normal'
    GRADE_POOR = 'poor'

    GRADE_CHOICES = [
        (GRADE_EXCELLENT, '优秀'),
        (GRADE_GOOD, '良好'),
        (GRADE_NORMAL, '合格'),
        (GRADE_POOR, '不合格'),
    ]

    batch = models.OneToOneField(
        HerbBatch, on_delete=models.CASCADE, related_name='quality_assessment', verbose_name='所属批次'
    )
    total_weight_loss_percent = models.DecimalField('总重量损耗率(%)', max_digits=5, decimal_places=2)
    avg_color_score = models.DecimalField('平均色泽评分', max_digits=3, decimal_places=1, default=0)
    abnormal_count = models.PositiveIntegerField('异常次数', default=0)
    abnormal_details = models.JSONField('异常详情列表', default=list, blank=True)
    steam_time_deviation = models.DecimalField('蒸制时间偏差率(%)', max_digits=5, decimal_places=2, default=0)
    dry_duration_deviation = models.DecimalField('晾晒时长偏差率(%)', max_digits=5, decimal_places=2, default=0)
    final_score = models.DecimalField('最终评分(满分100)', max_digits=5, decimal_places=2, default=0)
    overall_grade = models.CharField('综合评级', max_length=20, choices=GRADE_CHOICES, default=GRADE_NORMAL)
    evaluator = models.CharField('评估人', max_length=50, blank=True, null=True)
    evaluation_remark = models.TextField('评估备注', blank=True, null=True)
    created_at = models.DateTimeField('评估时间', auto_now_add=True)

    class Meta:
        verbose_name = '批次质量总评'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.batch.batch_no} - 评分{self.final_score}分'

    @classmethod
    def generate_assessment(cls, batch, evaluator='', remark=''):
        rounds = batch.rounds.all().order_by('round_no')
        if not rounds.exists():
            return None

        total_rounds = rounds.count()

        last_round = rounds.last()
        total_weight_loss = last_round.get_weight_loss_percent()

        color_map = {'excellent': 100, 'good': 85, 'normal': 70, 'abnormal': 40}
        color_scores = [color_map.get(r.color_rating, 50) for r in rounds]
        avg_color = round(sum(color_scores) / len(color_scores), 1)

        abnormal_rounds = []
        abnormal_count = 0
        total_steam_deviation = 0
        total_dry_deviation = 0
        standard_count = 0

        for r in rounds:
            if r.is_abnormal:
                abnormal_count += 1
                abnormal_rounds.append({
                    'round_no': r.round_no,
                    'reasons': list(r.abnormal_reasons.values()) if isinstance(r.abnormal_reasons, dict) else [str(r.abnormal_reasons)],
                    'handling_opinion': r.handling_opinion or '',
                })

            if batch.template_id:
                standard = batch.template.round_standards.filter(round_no=r.round_no).first()
                if standard:
                    standard_count += 1
                    steam_avg = (float(standard.steam_time_min) + float(standard.steam_time_max)) / 2
                    dry_avg = (float(standard.dry_duration_min) + float(standard.dry_duration_max)) / 2
                    if steam_avg > 0:
                        total_steam_deviation += abs(float(r.steam_time) - steam_avg) / steam_avg * 100
                    if dry_avg > 0:
                        total_dry_deviation += abs(float(r.dry_duration) - dry_avg) / dry_avg * 100

        steam_deviation = round(total_steam_deviation / standard_count, 2) if standard_count > 0 else 0
        dry_deviation = round(total_dry_deviation / standard_count, 2) if standard_count > 0 else 0

        score = 100
        weight_loss_penalty = max(0, (total_weight_loss - 15)) * 2
        score -= weight_loss_penalty

        color_penalty = (100 - avg_color) * 0.3
        score -= color_penalty

        abnormal_penalty = abnormal_count * 5
        score -= abnormal_penalty

        deviation_penalty = (steam_deviation + dry_deviation) * 0.2
        score -= deviation_penalty

        final_score = round(max(0, min(100, score)), 2)

        if final_score >= 90:
            grade = cls.GRADE_EXCELLENT
        elif final_score >= 75:
            grade = cls.GRADE_GOOD
        elif final_score >= 60:
            grade = cls.GRADE_NORMAL
        else:
            grade = cls.GRADE_POOR

        assessment, _ = cls.objects.update_or_create(
            batch=batch,
            defaults={
                'total_weight_loss_percent': round(total_weight_loss, 2),
                'avg_color_score': avg_color,
                'abnormal_count': abnormal_count,
                'abnormal_details': abnormal_rounds,
                'steam_time_deviation': steam_deviation,
                'dry_duration_deviation': dry_deviation,
                'final_score': final_score,
                'overall_grade': grade,
                'evaluator': evaluator,
                'evaluation_remark': remark,
            }
        )
        return assessment
