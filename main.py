from flask import Flask, request, jsonify
import os
import smtplib
import dns.resolver
import socket
import time
import random
import socks  # libreria PySocks

app = Flask(__name__)

# 🔌 Config Rotating Proxy Endpoint (Webshare)
PROXY_HOST = "p.webshare.io"
PROXY_PORT = 80
PROXY_USER = "xygajkdy-rotate"
PROXY_PASS = "yy7o17zu86pw"

# Attiva il proxy SOCKS5 per tutte le connessioni
socks.setdefaultproxy(
    socks.SOCKS5,
    PROXY_HOST,
    PROXY_PORT,
    True,
    PROXY_USER,
    PROXY_PASS
)
socket.socket = socks.socksocket

# ✉️ Identità mittente / HELO
MAIL_FROM = "n.vellani@consulenzadedicata.com"
HELO_DOMAIN = "mail.consulenzadedicata.com"

# Parametri vari
SMTP_TIMEOUT = 15
JITTER_MIN, JITTER_MAX = 0.15, 0.45
TRANSIENT_4XX = {421, 450, 451, 452, 454, 455}

def sleep_jitter():
    time.sleep(random.uniform(JITTER_MIN, JITTER_MAX))

@app.route("/check", methods=["GET"])
def check_email():
    email = request.args.get("email")
    if not email or "@" not in email:
        return jsonify({"status": "error", "reason": "Invalid email format"}), 400

    domain = email.split('@')[1]
    error_log = []

    # 1) MX lookup
    try:
        mx_records = dns.resolver.resolve(domain, 'MX')
        mx_hosts = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in mx_records])
    except Exception as e:
        return jsonify({"status": "error", "reason": f"No MX records found for domain: {domain}", "details": str(e)}), 400

    # 2) Tentativi sugli MX
    for pref, mx_host in mx_hosts:
        try:
            sleep_jitter()
            server = smtplib.SMTP(host=mx_host, port=25, timeout=SMTP_TIMEOUT, local_hostname=HELO_DOMAIN)
            server.set_debuglevel(0)

            try:
                server.ehlo()
            except:
                pass

            try:
                if server.has_extn("starttls"):
                    server.starttls()
                    server.ehlo()
            except:
                pass

            try:
                server.helo(HELO_DOMAIN)
            except:
                pass

            server.mail(MAIL_FROM)
            sleep_jitter()
            code, msg = server.rcpt(email)
            server.quit()

            msg_decoded = msg.decode() if isinstance(msg, bytes) else str(msg)

            if code == 250:
                return jsonify({"status": "valid", "mx": mx_host, "smtp_code": code, "smtp_response": msg_decoded})
            elif code == 550:
                return jsonify({"status": "invalid", "mx": mx_host, "smtp_code": code, "smtp_response": msg_decoded})
            else:
                return jsonify({
                    "status": "unknown",
                    "mx": mx_host,
                    "smtp_code": code,
                    "smtp_response": msg_decoded
                })

        except Exception as e:
            error_log.append({"mx": mx_host, "error": str(e)})
            continue

    return jsonify({
        "status": "error",
        "reason": "SMTP check failed on all MX",
        "errors": error_log
    }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
