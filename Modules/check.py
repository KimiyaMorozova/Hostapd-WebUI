import requests, time, os
host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
port = os.getenv("DASHBOARD_PORT", 5000)

def test_api():
    r = requests.get(f"http://{host}:{port}/api/hello")
    time.sleep(1)
    print ("Api Test: ", r.json())


