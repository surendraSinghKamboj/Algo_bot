import app.api.routes as routes
from fastapi.testclient import TestClient
from app.main import app

class StubClient:
    def authorization_url(self, state):
        return 'https://auth.example.com/authorize?state=' + state

routes.client_from_settings = lambda settings: StubClient()

import app.database.session as dbsession
class DummySession:
    def add(self, *a, **kw):
        return None
    def commit(self):
        return None
    def get(self, *a, **kw):
        return None
class DummyCtx:
    def __enter__(self):
        return DummySession()
    def __exit__(self, exc_type, exc, tb):
        return False

dbsession.SessionLocal = lambda: DummyCtx()

print('routes =', sorted([r.path for r in app.routes]))
with TestClient(app) as client:
    resp = client.get('/auth/upstox/login')
    print('status', resp.status_code)
    print('headers', resp.headers)
    print('text', resp.text)
