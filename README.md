# 羽毛球轮转工具

基于 Django 的双打轮转系统：报名、自动生成对阵、录入比分、排行榜与搭档胜率统计。

## 功能

- 创建活动（场地数、轮次、人数上限）
- 球员在线报名
- 一键生成双打轮转对阵（均衡轮空、减少重复搭档）
- 录入比分，自动更新活动状态
- 场次排行榜（胜场、胜率、净胜分）
- 每人搭档胜率统计
- 球员跨场次历史战绩

## 快速开始

在 PowerShell 中执行：

```powershell
cd C:\Users\69063\Projects\badminton-rotation
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

浏览器打开 http://127.0.0.1:8000/

## 使用流程

1. **创建活动** — 设置日期、场地数（如 2 片）、轮次（如 5 轮）
2. **报名** — 至少 4 人；人数不必是 4 的倍数，系统会自动安排轮空
3. **生成对阵** — 当 `min(报名人数, 场地数×4)` 向下取整后 ≥ 4 即可
4. **录入比分** — 在对阵表逐场录分
5. **查看排行榜** — 胜场排名 + 各球员搭档胜率

## 管理后台（可选）

```powershell
python manage.py createsuperuser
```

访问 http://127.0.0.1:8000/admin/

## 技术栈

- Django 5 + SQLite
- Bootstrap 5
