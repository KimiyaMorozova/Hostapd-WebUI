import threading
from collections import deque
from config import HISTORY_MINUTES, POLL_INTERVAL_SEC

lock = threading.Lock()
latest_status = {}
latest_clients = {}
client_count_history = deque(maxlen=HISTORY_MINUTES * max(1, int(60 / POLL_INTERVAL_SEC)))
recent_events = deque(maxlen=20000)
stop_event = threading.Event()
