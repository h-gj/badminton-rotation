import base64
import io
import json
import logging
import re
from datetime import date, datetime, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from rotation.forms import default_session_title
from rotation.models import Player, Registration, Session

logger = logging.getLogger(__name__)

VISION_PROMPT = """这是一张微信群「聊天信息」页面的截图。请提取以下信息，严格返回 JSON（不要 markdown）：

{
  "group_name": "群聊名称字段的完整文字",
  "members": ["成员昵称1", "成员昵称2"],
  "location": "球馆或场地名称，从群名推断",
  "event_date": "YYYY-MM-DD，从群名推断；只有月日则结合当前日期补全年份",
  "event_start_time": "HH:MM 24小时制",
  "event_end_time": "HH:MM 24小时制",
  "notes": "群名中除时间地点外的其他说明（如打折、打水等）"
}

规则：
1. members 只取成员网格中的昵称，不要包含「+」添加按钮
2. 昵称按截图原样保留，含省略号 … 或 ... 也保留
3. 群名常见格式如「7.9 周四晚荣达 8 到 11 打转打水 6折」：日期 7.9、地点荣达、晚 8 到 11 即 20:00-23:00
4. 若某项无法识别，字符串用空字符串，日期时间用 null
5. members 数组不要重复
"""


class WechatImportError(Exception):
    pass


def get_wechat_import_vision_providers():
    """返回已配置的视觉 API 列表，按优先级排序。"""
    providers = []

    def _add(name, api_key, api_base, model, json_mode):
        if not api_key:
            return
        providers.append({
            'name': name,
            'api_key': api_key,
            'api_base': api_base.rstrip('/'),
            'model': model,
            'json_mode': json_mode,
        })

    _add(
        '智谱',
        settings.WECHAT_IMPORT_VISION_API_KEY,
        settings.WECHAT_IMPORT_VISION_API_BASE,
        settings.WECHAT_IMPORT_VISION_MODEL,
        settings.WECHAT_IMPORT_VISION_JSON_MODE,
    )
    _add(
        '硅基流动',
        settings.WECHAT_IMPORT_VISION_BACKUP_1_API_KEY,
        settings.WECHAT_IMPORT_VISION_BACKUP_1_API_BASE,
        settings.WECHAT_IMPORT_VISION_BACKUP_1_MODEL,
        settings.WECHAT_IMPORT_VISION_BACKUP_1_JSON_MODE,
    )
    _add(
        '阿里云百炼',
        settings.WECHAT_IMPORT_VISION_BACKUP_2_API_KEY,
        settings.WECHAT_IMPORT_VISION_BACKUP_2_API_BASE,
        settings.WECHAT_IMPORT_VISION_BACKUP_2_MODEL,
        settings.WECHAT_IMPORT_VISION_BACKUP_2_JSON_MODE,
    )
    return providers


def _vision_configured():
    return bool(get_wechat_import_vision_providers())


def _vision_providers():
    return get_wechat_import_vision_providers()


def _call_vision_api(image_bytes, provider):
    encoded = base64.b64encode(prepare_image(image_bytes)).decode('ascii')
    payload = {
        'model': provider['model'],
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': VISION_PROMPT},
                {
                    'type': 'image_url',
                    'image_url': {'url': f'data:image/jpeg;base64,{encoded}'},
                },
            ],
        }],
        'temperature': 0.1,
    }
    if provider.get('json_mode'):
        payload['response_format'] = {'type': 'json_object'}

    req = Request(
        f"{provider['api_base']}/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f"Bearer {provider['api_key']}",
        },
        method='POST',
    )
    try:
        with urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode('utf-8'))
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise WechatImportError(detail) from exc
    except URLError as exc:
        raise WechatImportError(str(exc.reason)) from exc

    try:
        content = body['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise WechatImportError('返回格式异常') from exc

    content = content.strip()
    if content.startswith('```'):
        content = re.sub(r'^```(?:json)?\s*', '', content)
        content = re.sub(r'\s*```$', '', content)
    return json.loads(content)


def _call_vision_with_fallback(image_bytes):
    providers = _vision_providers()
    if not providers:
        raise WechatImportError(
            '未配置视觉识别 API。请在 .env 中设置 WECHAT_IMPORT_VISION_API_KEY，'
            '或配置备用 WECHAT_IMPORT_VISION_BACKUP_1_API_KEY（硅基流动）。'
        )

    errors = []
    for provider in providers:
        label = provider['name']
        try:
            logger.info('wechat import trying vision provider: %s', label)
            return _call_vision_api(image_bytes, provider)
        except WechatImportError as exc:
            detail = str(exc)
            errors.append(f'{label}：{detail[:120]}')
            logger.warning('vision provider %s failed: %s', label, detail[:200])
            continue
        except json.JSONDecodeError as exc:
            errors.append(f'{label}：返回内容不是有效 JSON')
            logger.warning('vision provider %s json decode failed', label)
            continue

    joined = '；'.join(errors)
    raise WechatImportError(
        f'所有视觉 API 均失败。{joined}。'
        '建议配置硅基流动或阿里云百炼备用 Key，或稍后再试。'
    )


def prepare_image(image_bytes):
    from PIL import Image

    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert('RGB')
    max_size = 1280
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def _parse_time_value(value):
    if not value:
        return None
    if isinstance(value, time):
        return value.replace(second=0, microsecond=0)
    text = str(value).strip()
    for fmt in ('%H:%M:%S', '%H:%M'):
        try:
            return datetime.strptime(text, fmt).time().replace(second=0, microsecond=0)
        except ValueError:
            continue
    return None


def _coerce_event_date(parsed, reference_date=None):
    """修正 Vision/手输里常见的错误年份（如 2023 写成活动日期）。"""
    if not parsed:
        return None
    reference_date = reference_date or timezone.localdate()
    if parsed.year < reference_date.year:
        try:
            parsed = parsed.replace(year=reference_date.year)
        except ValueError:
            parsed = parsed.replace(year=reference_date.year, day=28)
    if parsed < reference_date:
        try:
            next_year = parsed.replace(year=reference_date.year + 1)
            if next_year >= reference_date:
                parsed = next_year
        except ValueError:
            pass
    return parsed


def _parse_date_value(value, reference_date=None):
    reference_date = reference_date or timezone.localdate()
    if not value:
        return None
    if isinstance(value, date):
        return _coerce_event_date(value, reference_date)
    text = str(value).strip()
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            parsed = datetime.strptime(text, fmt).date()
            return _coerce_event_date(parsed, reference_date)
        except ValueError:
            continue
    m = re.search(r'(\d{1,2})\.(\d{1,2})', text)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = reference_date.year
        try:
            parsed = date(year, month, day)
            if parsed < reference_date:
                parsed = date(year + 1, month, day)
            return parsed
        except ValueError:
            return None
    return None


def parse_group_name_text(text, reference_date=None):
    """从群聊名称文本中补充解析时间、地点。"""
    reference_date = reference_date or timezone.localdate()
    result = {
        'location': '',
        'event_date': None,
        'event_start_time': None,
        'event_end_time': None,
        'notes': text or '',
    }
    if not text:
        return result

    parsed_date = _parse_date_value(text, reference_date)
    if parsed_date:
        result['event_date'] = parsed_date

    evening = '晚' in text
    time_match = re.search(r'(\d{1,2})\s*到\s*(\d{1,2})', text)
    if time_match:
        start_hour = int(time_match.group(1))
        end_hour = int(time_match.group(2))
        if evening and start_hour <= 12:
            start_hour += 12 if start_hour < 12 else 0
        if evening and end_hour <= 12:
            end_hour += 12 if end_hour < 12 else 0
        result['event_start_time'] = time(start_hour, 0)
        result['event_end_time'] = time(end_hour, 0)

    loc_match = re.search(r'周[一二三四五六日天]晚([^0-9\s到]+)', text)
    if loc_match:
        result['location'] = loc_match.group(1).strip(' ，、')
    elif not result['location']:
        generic = re.search(
            r'(?:^|\s)([\u4e00-\u9fff]{2,8})(?=\s+\d|\s+\d{1,2}\s*到)',
            text,
        )
        if generic:
            result['location'] = generic.group(1)

    return result


def _normalize_members(raw_members):
    members = []
    seen = set()
    skip_words = {'+', '添加', '邀请', '聊天信息'}
    for item in raw_members or []:
        if isinstance(item, dict):
            name = (item.get('nickname') or item.get('display_name') or item.get('name') or '').strip()
        else:
            name = str(item).strip()
        if not name or name in skip_words or name in seen:
            continue
        if name.startswith('+') or name in ('十',):
            continue
        seen.add(name)
        members.append(name)
    return members


def _merge_parsed(vision_data):
    reference_date = timezone.localdate()
    group_name = (vision_data.get('group_name') or '').strip()
    fallback = parse_group_name_text(group_name, reference_date)

    event_date = _parse_date_value(vision_data.get('event_date'), reference_date)
    if not event_date:
        event_date = fallback['event_date']

    start_time = _parse_time_value(vision_data.get('event_start_time'))
    end_time = _parse_time_value(vision_data.get('event_end_time'))
    if not start_time:
        start_time = fallback['event_start_time']
    if not end_time:
        end_time = fallback['event_end_time']
    if not start_time:
        start_time = time(20, 0)

    if event_date:
        event_date = _coerce_event_date(event_date, reference_date)

    location = (vision_data.get('location') or '').strip() or fallback['location']
    notes = (vision_data.get('notes') or '').strip() or group_name
    members = _normalize_members(vision_data.get('members'))

    return {
        'group_name': group_name,
        'location': location,
        'event_date': event_date.isoformat() if event_date else '',
        'event_start_time': start_time.strftime('%H:%M') if start_time else '',
        'event_end_time': end_time.strftime('%H:%M') if end_time else '',
        'notes': notes,
        'members': members,
    }


def parse_wechat_screenshot(image_bytes):
    if not _vision_configured():
        raise WechatImportError(
            '未配置视觉识别 API。请在环境变量中设置 WECHAT_IMPORT_VISION_API_KEY，'
            '可选 WECHAT_IMPORT_VISION_API_BASE、WECHAT_IMPORT_VISION_MODEL。'
        )
    if not image_bytes:
        raise WechatImportError('请上传截图')

    vision_data = _call_vision_with_fallback(image_bytes)
    return _merge_parsed(vision_data)


def match_player(nickname, club=None):
    nickname = (nickname or '').strip()
    if not nickname:
        return None

    qs = Player.objects.filter(club=club) if club else Player.objects.all()
    player = qs.filter(
        Q(nickname__iexact=nickname) | Q(name__iexact=nickname)
    ).first()
    if not player:
        player = qs.filter(nickname__icontains=nickname).first()
    if player:
        return {
            'nickname': nickname,
            'player_id': player.pk,
            'display_name': player.display_name,
            'matched': True,
        }
    return {
        'nickname': nickname,
        'player_id': None,
        'display_name': nickname,
        'matched': False,
    }


def build_import_preview(parsed, club=None):
    members = []
    for nick in parsed.get('members', []):
        item = match_player(nick, club=club)
        if item:
            members.append(item)
    return {
        **parsed,
        'members_detail': members,
        'member_count': len(members),
    }


def find_or_create_player(nickname, club=None):
    from rotation.services.player_provision import get_or_create_club_player

    nickname = (nickname or '').strip()
    if not nickname:
        return None
    if not club:
        matched = match_player(nickname)
        if matched and matched['player_id']:
            return Player.objects.get(pk=matched['player_id'])
        return Player.objects.create(name=nickname, nickname=nickname)
    player, _, _ = get_or_create_club_player(club, nickname, nickname=nickname)
    return player


def create_session_from_import(data, club=None):
    if not club:
        raise WechatImportError('请先创建俱乐部')
    reference_date = timezone.localdate()
    event_date = _parse_date_value(data.get('event_date'), reference_date)
    start_time = _parse_time_value(data.get('event_start_time')) or time(20, 0)
    end_time = _parse_time_value(data.get('event_end_time'))
    if not event_date:
        raise WechatImportError('请填写比赛日期')

    members = _normalize_members(data.get('members') or [])
    if isinstance(data.get('members'), str):
        members = _normalize_members(re.split(r'[\n,，\s]+', data['members']))
    if not members:
        raise WechatImportError('请至少添加一名球员')

    naive_start = datetime.combine(event_date, start_time)
    event_start = timezone.make_aware(naive_start, timezone.get_current_timezone())

    player_count = len(members)
    session = Session.objects.create(
        title=default_session_title(player_count),
        event_date=event_start,
        event_end_time=end_time,
        location=(data.get('location') or '').strip(),
        notes=(data.get('notes') or '').strip(),
        max_players=max(player_count, 8),
        club=club,
    )

    for nickname in members:
        player = find_or_create_player(nickname, club=club)
        if player:
            Registration.objects.get_or_create(session=session, player=player)

    count = session.registrations.count()
    if count:
        session.title = default_session_title(count)
        session.max_players = max(count, session.max_players)
        session.save(update_fields=['title', 'max_players'])

    return session
