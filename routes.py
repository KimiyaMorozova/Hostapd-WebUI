import time
import logging
from flask import jsonify, request
from state import lock, latest_clients, latest_status, recent_events, client_count_history, POLL_INTERVAL_SEC

logger = logging.getLogger("hostapd.routes")

def register_routes(app):
    @app.get("/api/clients")
    def api_clients():
        logger.debug("api_clients called: %s %s", request.method, request.path)
        with lock:
            data = {
                'ts': int(time.time()),
                'clients': latest_clients,
            }
        logger.debug("api_clients returning %d clients", len(data['clients']) if data['clients'] else 0)
        return jsonify(data)


    @app.get("/api/status")
    def api_status():
        logger.debug("api_status called")
        with lock:
            status = latest_status.copy()
            # enrich with live count
            status['live_num_sta'] = len(latest_clients)
        logger.debug("api_status live_num_sta=%d", status['live_num_sta'])
        return jsonify(status)


    @app.get("/api/summary")
    def api_summary():
        logger.debug("api_summary called")
        now = int(time.time())
        with lock:
            # events in last 24h
            connects = sum(1 for e in recent_events if e[1] == 'connected')
            disconnects = sum(1 for e in recent_events if e[1] == 'disconnected')
            # history lists
            hist = list(client_count_history)
            # sample every ~minute for chart simplicity
            sampled = hist[::max(1, int(60 / POLL_INTERVAL_SEC))]
            summary = {
                'ts': now,
                'connects_24h': connects,
                'disconnects_24h': disconnects,
                'history': sampled,
                'live_num_sta': len(latest_clients),
            }
        logger.debug("api_summary connects=%d disconnects=%d live=%d hist_len=%d", connects, disconnects, summary['live_num_sta'], len(sampled))
        return jsonify(summary)
