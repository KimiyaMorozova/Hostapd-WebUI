import subprocess

HOSTAPD_CLI = "/usr/sbin/hostapd_cli"  # oder aus .env lesen
IFACE = "wlan0"


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
        text = out.decode(errors="ignore").strip()

        print(text)

        return {
            "active": "Yes",
            "interface": IFACE,
            "ssid": data.get("ssid", "—"),
            "channel": data.get("channel", "—"),
            "frequency": data.get("freq", "—")
        }

    except Exception:
        return {"active": "No"}
