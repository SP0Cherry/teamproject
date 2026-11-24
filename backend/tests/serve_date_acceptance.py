"""Local browser acceptance: real API/services, isolated SQLite, frozen clock/model.

Run: python -m tests.serve_date_acceptance
Only binds 127.0.0.1:5181. Never imports this module from the production app.
Fixture login is acceptance / acceptance-only; no real credentials are used.
"""
import json
import tempfile
from contextlib import ExitStack, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
import uvicorn
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.response import error_response
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.notification import Notification
from app.models.todo import Todo
from app.services.date_context import capture_time
from app.services.extractor import extract_text
from app.services.notification_parser import extract_notification
import app.models as _models  # noqa: F401

SOURCE = '本周三下午三点提交替身报告；下周六上午十点参加替身会议；2026年11月20日全天整理替身资料；下午三点购买替身文具'
INSTANT = datetime(2026, 11, 8, 2, tzinfo=timezone.utc)
CONTEXT = capture_time(INSTANT)
DIST = Path(__file__).resolve().parents[2] / 'frontend' / 'dist'
REPORT = Path(__file__).resolve().parents[2] / 'docs/changes/fix-window-controls-and-date-aware-parsing/browser-acceptance.json'
state = {'file_attempts': 0, 'save_attempts': 0, 'model_calls': 0, 'notification_id': None}
session_factory = None


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return INSTANT.astimezone(tz) if tz else INSTANT.replace(tzinfo=None)


async def model_post(_client, url, **kwargs):
    # All model traffic is intercepted: any unexpected destination fails locally.
    assert str(url) == 'https://acceptance.invalid/v1/chat/completions'
    payload = kwargs['json']
    system = payload['messages'][0]['content']
    assert CONTEXT['request_sent_at'] in system and 'Asia/Shanghai' in system
    state['model_calls'] += 1
    segments = SOURCE.split('；')
    rows = [
        {'title': '提交替身报告', 'date_expression': '本周三', 'time': '15:00', 'source_text': segments[0]},
        {'title': '参加替身会议', 'date_expression': '下周六', 'time': '10:00', 'source_text': segments[1]},
        {'title': '整理替身资料', 'date': '2026-11-20', 'source_text': segments[2]},
        {'title': '购买替身文具', 'time': '15:00', 'source_text': segments[3]},
    ]
    if '通知语义' in system:
        rows = [{**r, 'text': r['title']} for r in rows]
        content = {'title': '替身通知', 'content': '合成验收', 'items': rows}
    else:
        content = {'todos': rows}
    return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps(content)}}]}, request=httpx.Request('POST', str(url)))


def flaky_extract(path, mime):
    state['file_attempts'] += 1
    if state['file_attempts'] == 1:
        return '', '合成验收：首次提取失败，请重新上传同一文件'
    return extract_text(path, mime)


@asynccontextmanager
async def acceptance_lifespan(_app):
    global session_factory
    if not (DIST / 'index.html').is_file():
        raise RuntimeError('Build frontend first: cd frontend && npm run build')
    with tempfile.TemporaryDirectory(prefix='teamproject-date-acceptance-') as temp, ExitStack() as patches:
        root = Path(temp)
        upload = root / 'uploads'
        upload.mkdir()
        fixture = root / 'date-acceptance.txt'
        fixture.write_text(SOURCE, encoding='utf-8')
        engine = create_async_engine('sqlite+aiosqlite:///' + (root / 'acceptance.db').as_posix())
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async def isolated_db():
            async with session_factory() as session:
                yield session
        app.dependency_overrides[get_db] = isolated_db
        for key, value in {'llm_api_key': 'fixture-only', 'llm_base_url': 'https://acceptance.invalid/v1', 'llm_model': 'local-double', 'upload_dir': str(upload)}.items():
            patches.enter_context(patch.object(settings, key, value))
        for module in ['app.services.model', 'app.services.todo_parser', 'app.services.notification_parser']:
            patches.enter_context(patch(module + '.capture_time', side_effect=lambda: dict(CONTEXT)))
        patches.enter_context(patch('app.services.home.datetime', FrozenDateTime))
        patches.enter_context(patch('app.services.model.httpx.AsyncClient.post', new=model_post))
        patches.enter_context(patch('app.api.v1.todos.extract_text', side_effect=flaky_extract))
        async with session_factory() as session:
            user = User(id='acceptance-user', username='acceptance', password_hash=hash_password('acceptance-only'))
            session.add(user)
            session.add(User(id='other-user', username='other-acceptance', password_hash=hash_password('acceptance-only')))
            parsed = await extract_notification(SOURCE)
            notification = Notification(owner_id=user.id, source='isolated-fixture', raw_text=SOURCE, parsed=json.dumps(parsed))
            session.add(notification)
            await session.commit()
            state['notification_id'] = notification.id
        print(json.dumps({'url': 'http://localhost:5181', 'fixture_file': str(fixture), 'notification_id': state['notification_id']}, ensure_ascii=False), flush=True)
        try:
            yield
        finally:
            app.dependency_overrides.clear()
            await engine.dispose()


app.router.lifespan_context = acceptance_lifespan


@app.middleware('http')
async def first_save_failure(request, call_next):
    if request.url.path == '/api/v1/todos/batch-create' and request.method == 'POST':
        state['save_attempts'] += 1
        if state['save_attempts'] == 1:
            return error_response(code='DEPENDENCY_UNAVAILABLE', message='合成验收：首次保存失败，请保留编辑后重试', status=503, request_id='isolated-fixture')
    return await call_next(request)


@app.get('/__acceptance/report')
async def acceptance_report():
    # Public only in this explicit loopback fixture process; synthetic data only.
    async with session_factory() as session:
        rows = list((await session.execute(select(Todo).order_by(Todo.title))).scalars())
    from app.services.date_context import serialize_todo
    report = {**state, 'clock': CONTEXT, 'todos': [serialize_todo(row) for row in rows]}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return report


app.router.routes = [route for route in app.router.routes if getattr(route, 'path', None) != '/']
app.mount('/assets', StaticFiles(directory=DIST / 'assets'), name='acceptance-assets')


@app.get('/{path:path}')
async def frontend(path: str):
    if path.startswith('api/'):
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse(DIST / 'index.html')


if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=5181, access_log=False, log_level='warning')
