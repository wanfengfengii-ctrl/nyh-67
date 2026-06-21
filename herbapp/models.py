from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


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

    batch = models.ForeignKey(
        HerbBatch, on_delete=models.CASCADE, related_name='rounds', verbose_name='所属批次'
    )
    round_no = models.PositiveIntegerField('轮次序号')
    steam_time = models.DecimalField('蒸制时间(分钟)', max_digits=6, decimal_places=1)
    dry_duration = models.DecimalField('晾晒时长(小时)', max_digits=6, decimal_places=1)
    weight = models.DecimalField('当前重量(g)', max_digits=10, decimal_places=2)
    color_rating = models.CharField('色泽评级', max_length=20, choices=COLOR_CHOICES)
    handling_opinion = models.TextField('处理意见', blank=True, null=True)
    record_time = models.DateTimeField('记录时间', auto_now_add=True)

    class Meta:
        verbose_name = '炮制轮次'
        verbose_name_plural = verbose_name
        ordering = ['batch', 'round_no']
        unique_together = [('batch', 'round_no')]

    def __str__(self):
        return f'{self.batch.batch_no} - 第{self.round_no}轮'

    def clean(self):
        if self.steam_time is not None and self.steam_time <= 0:
            raise ValidationError({'steam_time': '蒸制时间必须大于0'})
        if self.dry_duration is not None and self.dry_duration <= 0:
            raise ValidationError({'dry_duration': '晾晒时长必须大于0'})
        if self.weight is not None:
            if self.weight <= 0:
                raise ValidationError({'weight': '当前重量必须大于0'})
            if self.batch_id and self.weight > self.batch.initial_weight:
                raise ValidationError({'weight': '当前重量不能大于初始重量'})
        if self.color_rating == self.COLOR_ABNORMAL and not self.handling_opinion:
            raise ValidationError({'handling_opinion': '色泽评级异常时必须填写处理意见'})


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
