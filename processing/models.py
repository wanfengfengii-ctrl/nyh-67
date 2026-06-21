from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from herbapp.models import HerbBatch, ProcessingRound


class EnvironmentStandard(models.Model):
    PARAM_TYPE_TEMPERATURE = 'temperature'
    PARAM_TYPE_HUMIDITY = 'humidity'

    PARAM_TYPE_CHOICES = [
        (PARAM_TYPE_TEMPERATURE, '温度'),
        (PARAM_TYPE_HUMIDITY, '湿度'),
    ]

    STAGE_STEAM = 'steam'
    STAGE_DRY = 'dry'
    STAGE_BOTH = 'both'

    STAGE_CHOICES = [
        (STAGE_STEAM, '蒸制阶段'),
        (STAGE_DRY, '晾晒阶段'),
        (STAGE_BOTH, '全部阶段'),
    ]

    herb_name = models.CharField('适用药材', max_length=100)
    param_type = models.CharField('参数类型', max_length=20, choices=PARAM_TYPE_CHOICES)
    stage = models.CharField('适用阶段', max_length=20, choices=STAGE_CHOICES, default=STAGE_BOTH)
    min_value = models.DecimalField('最小值', max_digits=6, decimal_places=2)
    max_value = models.DecimalField('最大值', max_digits=6, decimal_places=2)
    unit = models.CharField('单位', max_length=10, default='')
    description = models.TextField('说明', blank=True, null=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '环境参数标准'
        verbose_name_plural = verbose_name
        ordering = ['herb_name', 'param_type', 'stage']

    def __str__(self):
        stage_display = dict(self.STAGE_CHOICES).get(self.stage, '')
        return f'{self.herb_name} - {self.get_param_type_display()}({stage_display})'

    def clean(self):
        errors = {}
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                errors['max_value'] = '最大值不能小于最小值'
        if self.param_type == self.PARAM_TYPE_TEMPERATURE and not self.unit:
            self.unit = '°C'
        if self.param_type == self.PARAM_TYPE_HUMIDITY and not self.unit:
            self.unit = '%RH'
        if errors:
            raise ValidationError(errors)

    def check_value(self, value):
        if value is None:
            return False, '参数值为空'
        is_normal = self.min_value <= value <= self.max_value
        if not is_normal:
            if value < self.min_value:
                return False, f'{value}{self.unit}低于标准下限{self.min_value}{self.unit}'
            else:
                return False, f'{value}{self.unit}超出标准上限{self.max_value}{self.unit}'
        return True, '正常'


class EnvironmentRecord(models.Model):
    batch = models.ForeignKey(
        HerbBatch, on_delete=models.CASCADE, related_name='env_records', verbose_name='所属批次'
    )
    round_no = models.PositiveIntegerField('关联轮次', blank=True, null=True)
    record_time = models.DateTimeField('记录时间', default=timezone.now)
    temperature = models.DecimalField('温度(°C)', max_digits=6, decimal_places=2, blank=True, null=True)
    humidity = models.DecimalField('湿度(%RH)', max_digits=6, decimal_places=2, blank=True, null=True)
    location = models.CharField('监测位置', max_length=100, blank=True, null=True)
    recorder = models.CharField('记录人', max_length=50, blank=True, null=True)
    is_abnormal = models.BooleanField('是否异常', default=False)
    abnormal_details = models.JSONField('异常详情', default=dict, blank=True)
    handling_opinion = models.TextField('处理意见', blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)

    class Meta:
        verbose_name = '环境监测记录'
        verbose_name_plural = verbose_name
        ordering = ['-record_time']

    def __str__(self):
        return f'{self.batch.batch_no} - {self.record_time.strftime("%Y-%m-%d %H:%M")}'

    def detect_abnormalities(self):
        abnormalities = {}
        is_abnormal = False

        if self.batch_id:
            standards = EnvironmentStandard.objects.filter(
                herb_name=self.batch.herb_name,
                is_active=True
            )

            if self.temperature is not None:
                temp_standards = standards.filter(param_type=EnvironmentStandard.PARAM_TYPE_TEMPERATURE)
                for std in temp_standards:
                    is_normal, msg = std.check_value(float(self.temperature))
                    if not is_normal:
                        abnormalities[f'temperature_{std.stage}'] = msg
                        is_abnormal = True

            if self.humidity is not None:
                hum_standards = standards.filter(param_type=EnvironmentStandard.PARAM_TYPE_HUMIDITY)
                for std in hum_standards:
                    is_normal, msg = std.check_value(float(self.humidity))
                    if not is_normal:
                        abnormalities[f'humidity_{std.stage}'] = msg
                        is_abnormal = True

        self.is_abnormal = is_abnormal
        self.abnormal_details = abnormalities
        return is_abnormal, abnormalities

    def clean(self):
        if self.temperature is None and self.humidity is None:
            raise ValidationError('温度和湿度不能同时为空')

        is_abnormal, abnormalities = self.detect_abnormalities()
        if is_abnormal and not self.handling_opinion:
            raise ValidationError({'handling_opinion': '检测到环境参数异常，必须填写处理意见'})


class Equipment(models.Model):
    TYPE_STEAMER = 'steamer'
    TYPE_DRYING_RACK = 'drying_rack'
    TYPE_OTHER = 'other'

    TYPE_CHOICES = [
        (TYPE_STEAMER, '蒸制设备'),
        (TYPE_DRYING_RACK, '晾晒架'),
        (TYPE_OTHER, '其他设备'),
    ]

    STATUS_NORMAL = 'normal'
    STATUS_MAINTENANCE = 'maintenance'
    STATUS_FAULT = 'fault'
    STATUS_SCRAPPED = 'scrapped'

    STATUS_CHOICES = [
        (STATUS_NORMAL, '正常'),
        (STATUS_MAINTENANCE, '维护中'),
        (STATUS_FAULT, '故障'),
        (STATUS_SCRAPPED, '已报废'),
    ]

    equipment_no = models.CharField('设备编号', max_length=50, unique=True)
    equipment_name = models.CharField('设备名称', max_length=100)
    equipment_type = models.CharField('设备类型', max_length=20, choices=TYPE_CHOICES)
    model = models.CharField('规格型号', max_length=100, blank=True, null=True)
    manufacturer = models.CharField('生产厂家', max_length=100, blank=True, null=True)
    purchase_date = models.DateField('购置日期', blank=True, null=True)
    location = models.CharField('存放位置', max_length=100, blank=True, null=True)
    status = models.CharField('设备状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_NORMAL)
    capacity = models.CharField('额定容量', max_length=50, blank=True, null=True)
    last_maintenance_date = models.DateField('上次维护日期', blank=True, null=True)
    next_maintenance_date = models.DateField('下次维护日期', blank=True, null=True)
    description = models.TextField('设备说明', blank=True, null=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '设备信息'
        verbose_name_plural = verbose_name
        ordering = ['equipment_type', 'equipment_no']

    def __str__(self):
        return f'{self.equipment_no} - {self.equipment_name}'


class EquipmentStatusRecord(models.Model):
    STATUS_RUNNING = 'running'
    STATUS_STANDBY = 'standby'
    STATUS_STOPPED = 'stopped'
    STATUS_FAULT = 'fault'

    STATUS_CHOICES = [
        (STATUS_RUNNING, '运行中'),
        (STATUS_STANDBY, '待机'),
        (STATUS_STOPPED, '停机'),
        (STATUS_FAULT, '故障'),
    ]

    batch = models.ForeignKey(
        HerbBatch, on_delete=models.CASCADE, related_name='equipment_records', verbose_name='所属批次'
    )
    round_no = models.PositiveIntegerField('关联轮次', blank=True, null=True)
    equipment = models.ForeignKey(
        Equipment, on_delete=models.PROTECT, related_name='status_records', verbose_name='设备'
    )
    record_time = models.DateTimeField('记录时间', default=timezone.now)
    running_status = models.CharField('运行状态', max_length=20, choices=STATUS_CHOICES)
    operating_params = models.JSONField('运行参数', default=dict, blank=True)
    is_abnormal = models.BooleanField('是否异常', default=False)
    abnormal_description = models.TextField('异常说明', blank=True, null=True)
    handling_result = models.TextField('处理结果', blank=True, null=True)
    operator = models.CharField('操作人员', max_length=50, blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)

    class Meta:
        verbose_name = '设备状态记录'
        verbose_name_plural = verbose_name
        ordering = ['-record_time']

    def __str__(self):
        return f'{self.equipment.equipment_no} - {self.record_time.strftime("%Y-%m-%d %H:%M")}'

    def detect_abnormalities(self):
        is_abnormal = False
        if self.running_status == self.STATUS_FAULT:
            is_abnormal = True
        elif self.equipment_id and self.equipment.status == Equipment.STATUS_FAULT:
            is_abnormal = True

        self.is_abnormal = is_abnormal
        return is_abnormal

    def clean(self):
        self.detect_abnormalities()
        if self.is_abnormal and not self.handling_result:
            raise ValidationError({'handling_result': '设备状态异常，必须填写处理结果'})
        if self.running_status == self.STATUS_FAULT and not self.abnormal_description:
            raise ValidationError({'abnormal_description': '设备故障时必须填写异常说明'})


class DryingAreaRecord(models.Model):
    AREA_TYPE_SUNSHINE = 'sunshine'
    AREA_TYPE_SHADE = 'shade'
    AREA_TYPE_VENTILATED = 'ventilated'
    AREA_TYPE_CONSTANT_TEMP = 'constant_temp'

    AREA_TYPE_CHOICES = [
        (AREA_TYPE_SUNSHINE, '阳光晾晒区'),
        (AREA_TYPE_SHADE, '阴干区'),
        (AREA_TYPE_VENTILATED, '通风区'),
        (AREA_TYPE_CONSTANT_TEMP, '恒温区'),
    ]

    batch = models.ForeignKey(
        HerbBatch, on_delete=models.CASCADE, related_name='drying_records', verbose_name='所属批次'
    )
    round_no = models.PositiveIntegerField('关联轮次', blank=True, null=True)
    record_time = models.DateTimeField('记录时间', default=timezone.now)
    area_name = models.CharField('区域名称', max_length=100)
    area_type = models.CharField('区域类型', max_length=20, choices=AREA_TYPE_CHOICES)
    temperature = models.DecimalField('区域温度(°C)', max_digits=6, decimal_places=2, blank=True, null=True)
    humidity = models.DecimalField('区域湿度(%RH)', max_digits=6, decimal_places=2, blank=True, null=True)
    light_intensity = models.DecimalField('光照强度(Lux)', max_digits=8, decimal_places=2, blank=True, null=True)
    wind_speed = models.DecimalField('风速(m/s)', max_digits=5, decimal_places=2, blank=True, null=True)
    ventilation_condition = models.CharField('通风情况', max_length=200, blank=True, null=True)
    position_info = models.CharField('具体位置', max_length=200, blank=True, null=True)
    is_abnormal = models.BooleanField('是否异常', default=False)
    abnormal_details = models.JSONField('异常详情', default=dict, blank=True)
    handling_opinion = models.TextField('处理意见', blank=True, null=True)
    recorder = models.CharField('记录人', max_length=50, blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)

    class Meta:
        verbose_name = '晾晒区域记录'
        verbose_name_plural = verbose_name
        ordering = ['-record_time']

    def __str__(self):
        return f'{self.batch.batch_no} - {self.area_name}'

    def detect_abnormalities(self):
        abnormalities = {}
        is_abnormal = False

        if self.batch_id:
            standards = EnvironmentStandard.objects.filter(
                herb_name=self.batch.herb_name,
                is_active=True,
                stage__in=[EnvironmentStandard.STAGE_DRY, EnvironmentStandard.STAGE_BOTH]
            )

            if self.temperature is not None:
                temp_standards = standards.filter(param_type=EnvironmentStandard.PARAM_TYPE_TEMPERATURE)
                for std in temp_standards:
                    is_normal, msg = std.check_value(float(self.temperature))
                    if not is_normal:
                        abnormalities['temperature'] = msg
                        is_abnormal = True

            if self.humidity is not None:
                hum_standards = standards.filter(param_type=EnvironmentStandard.PARAM_TYPE_HUMIDITY)
                for std in hum_standards:
                    is_normal, msg = std.check_value(float(self.humidity))
                    if not is_normal:
                        abnormalities['humidity'] = msg
                        is_abnormal = True

        self.is_abnormal = is_abnormal
        self.abnormal_details = abnormalities
        return is_abnormal, abnormalities

    def clean(self):
        is_abnormal, abnormalities = self.detect_abnormalities()
        if is_abnormal and not self.handling_opinion:
            raise ValidationError({'handling_opinion': '检测到晾晒区域条件异常，必须填写处理意见'})


class InspectionRecord(models.Model):
    INSPECTION_TYPE_DAILY = 'daily'
    INSPECTION_TYPE_BEFORE = 'before'
    INSPECTION_TYPE_AFTER = 'after'
    INSPECTION_TYPE_SPECIAL = 'special'

    INSPECTION_TYPE_CHOICES = [
        (INSPECTION_TYPE_DAILY, '日常巡检'),
        (INSPECTION_TYPE_BEFORE, '生产前检查'),
        (INSPECTION_TYPE_AFTER, '生产后检查'),
        (INSPECTION_TYPE_SPECIAL, '专项巡检'),
    ]

    RESULT_NORMAL = 'normal'
    RESULT_ABNORMAL = 'abnormal'
    RESULT_PENDING = 'pending'

    RESULT_CHOICES = [
        (RESULT_NORMAL, '正常'),
        (RESULT_ABNORMAL, '异常'),
        (RESULT_PENDING, '待确认'),
    ]

    batch = models.ForeignKey(
        HerbBatch, on_delete=models.CASCADE, related_name='inspection_records', verbose_name='所属批次',
        blank=True, null=True
    )
    equipment = models.ForeignKey(
        Equipment, on_delete=models.SET_NULL, related_name='inspection_records', verbose_name='巡检设备',
        blank=True, null=True
    )
    inspection_type = models.CharField('巡检类型', max_length=20, choices=INSPECTION_TYPE_CHOICES)
    inspection_time = models.DateTimeField('巡检时间', default=timezone.now)
    inspector = models.CharField('巡检人', max_length=50)
    inspection_items = models.JSONField('巡检项目', default=list, blank=True)
    inspection_result = models.CharField('巡检结果', max_length=20, choices=RESULT_CHOICES, default=RESULT_PENDING)
    abnormal_description = models.TextField('异常说明', blank=True, null=True)
    handling_result = models.TextField('处理结果', blank=True, null=True)
    handling_person = models.CharField('处理人', max_length=50, blank=True, null=True)
    handling_time = models.DateTimeField('处理时间', blank=True, null=True)
    remark = models.TextField('备注', blank=True, null=True)
    images = models.JSONField('巡检图片', default=list, blank=True)

    class Meta:
        verbose_name = '巡检记录'
        verbose_name_plural = verbose_name
        ordering = ['-inspection_time']

    def __str__(self):
        return f'{self.get_inspection_type_display()} - {self.inspection_time.strftime("%Y-%m-%d %H:%M")}'

    def clean(self):
        if self.inspection_result == self.RESULT_ABNORMAL:
            if not self.abnormal_description:
                raise ValidationError({'abnormal_description': '巡检结果异常时必须填写异常说明'})
            if not self.handling_result:
                raise ValidationError({'handling_result': '巡检结果异常时必须填写处理结果'})
