from backend.app.core.config import Settings, settings
from fastapi.testclient import TestClient
from backend.app.main import app

s = Settings()
print('APP_NAME=', s.APP_NAME)
print('APP_ENV=', s.APP_ENV)
print('DEBUG=', type(s.DEBUG), s.DEBUG)
print('API_V1_PREFIX=', s.API_V1_PREFIX)

client = TestClient(app)
r = client.get('/health')
print('HEALTH status:', r.status_code)
print('HEALTH body:', r.json())
