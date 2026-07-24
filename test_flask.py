from app import app
from flask import session

app.config['TESTING'] = True
client = app.test_client()

with client.session_transaction() as sess:
    sess['user_id'] = 1

response = client.get('/reports/by-salesman?date_from=2026-07-02&date_to=2026-07-31')
print(response.status_code)
print(response.text)
