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


def get_connected_devices():
    """
    Holt die Liste der verbundenen Geräte.
    Gibt eine Liste von Dicts mit MAC, Signal, TX/RX Rates, etc. zurück.
    """
    try:
        # Zuerst alle MAC-Adressen der verbundenen Stationen holen
        out = subprocess.check_output(
            [HOSTAPD_CLI, "-i", IFACE, "all_sta"],
            stderr=subprocess.STDOUT,
            timeout=3
        )
        macs = out.decode("utf-8").strip().split("\n")
        macs = [mac.strip() for mac in macs if mac.strip()]

        devices = []
        for mac in macs:
            try:
                # Details für jede Station holen
                out = subprocess.check_output(
                    [HOSTAPD_CLI, "-i", IFACE, "sta", mac],
                    stderr=subprocess.STDOUT,
                    timeout=3
                )
                data = out.decode("utf-8").strip().split("\n")
                data = {k: v for k, v in (line.split("=", 1) for line in data if "=" in line)}
                data = {k.strip(): v.strip() for k, v in data.items()}

                device = {
                    "mac": mac,
                    "signal": data.get("signal", "—"),
                    "tx_rate": data.get("tx bitrate", "—"),
                    "rx_rate": data.get("rx bitrate", "—"),
                    "tx_packets": data.get("tx packets", "—"),
                    "rx_packets": data.get("rx packets", "—"),
                    "tx_bytes": data.get("tx bytes", "—"),
                    "rx_bytes": data.get("rx bytes", "—"),
                    "connected_time": data.get("connected time", "—"),
                    "auth": data.get("flags", "—"),
                    "inactive": data.get("inactive time", "—")
                }
                devices.append(device)
            except Exception as e:
                print(f"Fehler beim Holen der Daten für MAC {mac}: {e}")
                continue

        return devices

    except Exception as e:
        print(f"Fehler beim Holen der verbundenen Geräte: {e}")
        return []
