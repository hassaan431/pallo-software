import requests

try:
    res = requests.get('http://127.0.0.1:5000/products/search?q=AFGHAN')
    print("API Response:", res.status_code)
    print("Data:", res.json()[:2])
except Exception as e:
    print(e)
