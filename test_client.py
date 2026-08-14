from app import app
with app.test_client() as client:
    resp = client.post('/login', data={'username': 'admin', 'password': 'password123'})
    try:
        response = client.get('/dashboard')
        print("Status:", response.status_code)
        if response.status_code == 500:
            print(response.data.decode('utf-8'))
    except Exception as e:
        import traceback
        traceback.print_exc()
