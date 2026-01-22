import subprocess
import os
import re
from datetime import datetime, timedelta
HOSTAPD_CLI = "/usr/sbin/hostapd_cli"  # oder aus .env lesen
IFACE = os.getenv("HOSTAPD_IFACE", "wlx1cbfce77e19b")


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
    Holt die Liste der verbundenen Geräte MACs.
    Gibt eine Liste von MAC-Adressen zurück.
    """
    try:
        # Zuerst alle MAC-Adressen der verbundenen Stationen holen
        out = subprocess.check_output(
            [HOSTAPD_CLI, "-i", IFACE, "all_sta"],
            stderr=subprocess.STDOUT,
            timeout=3
        )
        macs = out.decode("utf-8").strip().split("\n")
        # Filtere nur gültige MAC-Adressen (Format XX:XX:XX:XX:XX:XX)
        macs = [mac.strip() for mac in macs if re.match(r'^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$', mac.strip())]
        return macs

    except Exception as e:
        print(f"Fehler beim Holen der verbundenen Geräte: {e}")
        return []


def get_device_info(mac):
    """
    Holt die Details zu einem verbundenen Gerät anhand der MAC-Adresse.
    Gibt ein Dict mit den wichtigsten Werten zurück.
    """
    try:
        out = subprocess.check_output(
            [HOSTAPD_CLI, "-i", IFACE, "sta", mac],
            stderr=subprocess.STDOUT,
            timeout=3
        )
        lines = out.decode("utf-8").strip().split("\n")
        data = {k: v for k, v in (line.split('=', 1) for line in lines if '=' in line)}
        # Werte extrahieren und ggf. umbenennen/umrechnen
        return {
            "mac": mac,
            "signal": data.get("signal", "—"),
            "tx_rate": data.get("tx_rate_info", "—"),
            "rx_rate": data.get("rx_rate_info", "—"),
            "tx_packets": data.get("tx_packets", "—"),
            "rx_packets": data.get("rx_packets", "—"),
            "tx_bytes": data.get("tx_bytes", "—"),
            "rx_bytes": data.get("rx_bytes", "—"),
            "connected_time": data.get("connected_time", "—"),
            "auth": data.get("authenticated", "—"),
            "inactive": data.get("inactive_msec", "—")
        }
    except Exception as e:
        print(f"Fehler beim Holen der Gerätedetails für {mac}: {e}")
        return {"mac": mac}


def get_24h_events():
    """
    Parst die hostapd Logs für Connect/Disconnect Events der letzten 24h.
    Verwendet journalctl, da Logs in systemd journal sind.
    Gibt ein Dict mit connected und disconnected zurück.
    """
    connected = 0
    disconnected = 0

    try:
        # journalctl für hostapd Unit, letzte 24h, grep für STA Events
        result = subprocess.run(
            ["journalctl", "-u", "hostapd", "--since", "24 hours ago", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.split('\n')
        for line in lines:
            if "IEEE 802.11: associated" in line:
                connected += 1
            elif "IEEE 802.11: disassociated" in line:
                disconnected += 1
    except subprocess.TimeoutExpired:
        print("journalctl timeout")
    except FileNotFoundError:
        print("journalctl not found, trying syslog")
        # Fallback to syslog if journalctl not available
        try:
            with open("/var/log/syslog", 'r') as f:
                lines = f.readlines()[-5000:]
                cutoff = datetime.now() - timedelta(hours=24)
                for line in lines:
                    if "AP-STA-CONNECTED" in line:
                        connected += 1
                    elif "AP-STA-DISCONNECTED" in line:
                        disconnected += 1
        except:
            pass
    except Exception as e:
        print(f"Error getting events: {e}")

    return {"connected": connected, "disconnected": disconnected}
