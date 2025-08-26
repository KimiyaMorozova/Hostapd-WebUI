import subprocess
import os
HOSTAPD_CLI = "/usr/sbin/hostapd_cli"  # oder aus .env lesen
IFACE = os.getenv("HOSTAPD_IFACE", "wlan0")


def hostapd_status():
    """
    Holt den aktuellen Status von hostapd.
    Gibt ein Dict mit Active, Interface, SSID, Channel, Frequency zurück.
    """
    try:
        out = subprocess.check_output(
            [HOSTAPD_CLI, "-i", IFACE, "status"],
            stderr=subprocess.STDOUT,
            timeout=3
        )
        data = out.decode("utf-8").strip().split("\n")
        data = {k: v for k, v in (line.split("=", 1) for line in data if "=" in line)} # each value gets a assinge
        data = {k.strip(): v.strip() for k, v in data.items()}  # remove whitespace


        return {
            "active": "Yes",
            "interface": IFACE,
            "ssid": data.get("ssid[0]", "—"),
            "channel": data.get("channel", "—"),
            "frequency": data.get("freq", "—")
        }

    except Exception:
        return {"active": "No"}
