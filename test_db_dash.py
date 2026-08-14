from app import app
with app.test_request_context('/dashboard'):
    from app import dashboard
    try:
        res = dashboard.__wrapped__()
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()
