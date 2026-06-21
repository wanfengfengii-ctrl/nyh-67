## 1. 架构设计

```mermaid
flowchart LR
    A["浏览器 (Django Templates"] --> B["Django Views"]
    B --> C["Django ORM"]
    C --> D["SQLite 数据库"]
    B --> E["业务验证层"]
    E --> F["表单验证 (Forms"]
    A --> G["前端图表 (Chart.js)"]
```

## 2. 技术栈
- 后端：Python 3.10+、Django 4.2 LTS
- 前端：Django Templates + Bootstrap 5
- 数据库：SQLite（开发环境）
- 图表：Chart.js（CDN 引入）
- 样式：Bootstrap 5 + 自定义 CSS

## 3. 路由定义
| 路由 | 视图 | 用途 |
|------|------|------|
| / | BatchListView | 批次列表首页 |
| /batch/create/ | BatchCreateView | 新建批次 |
| /batch/<int:pk>/ | BatchDetailView | 批次详情 |
| /batch/<int:pk>/round/create/ | RoundCreateView | 新增炮制轮次 |
| /batch/<int:pk>/accept/ | AcceptanceView | 提交验收 |
| /batch/<int:pk>/chart/ | BatchChartView | 图表数据 API |

## 4. 数据模型

```mermaid
erDiagram
    HERB_BATCH ||--o{ PROCESSING_ROUND : has
    HERB_BATCH ||--o| ACCEPTANCE : has
    HERB_BATCH {
        string batch_no PK "批次编号"
        string herb_name "药材名称"
        decimal initial_weight "初始重量(g)"
        int required_rounds "规定轮次"
        date created_at "创建日期"
        string status "状态"
    }
    PROCESSING_ROUND {
        int id PK
        int round_no "轮次序号"
        decimal steam_time "蒸制时间(分钟)"
        decimal dry_duration "晾晒时长(小时)"
        decimal weight "当前重量(g)"
        string color_rating "色泽评级"
        string handling_opinion "处理意见"
        date record_time "记录时间"
    }
    ACCEPTANCE {
        int id PK
        string result "验收结果"
        text remark "验收备注"
        date accepted_at "验收日期"
    }
```

## 5. 核心验证规则
1. 批次编号唯一且不重复
2. 蒸制时间 > 0
3. 晾晒时长 > 0
4. 当前重量 ≤ 初始重量
5. 轮次序号按顺序递增
6. 未完成规定轮次不可验收
7. 色泽评级异常必须填写处理意见

## 6. 项目结构
```
nyh-67/
├── manage.py
├── requirements.txt
├── herb_processing/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── processing/
    ├── models.py
    ├── forms.py
    ├── views.py
    ├── urls.py
    ├── admin.py
    └── templates/
        └── processing/
            ├── base.html
            ├── batch_list.html
            ├── batch_detail.html
            ├── batch_form.html
            ├── round_form.html
            └── acceptance_form.html
```
