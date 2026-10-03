import os
import time
import json
import threading
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# ==============================================================================
# ☁️ 7/24 ÜCRETSİZ BULUT SMC %85 WIN RATE PERPETUAL (.P) BOTU
# ==============================================================================
SYMBOLS    = ["ETHUSDT", "BTCUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT", "SUIUSDT"]
TIMEFRAMES = ["15m", "1h", "4h"]

WALLET_USD = 100.0
RISK_USD   = 5.0
RR_RATIO   = 2.2
TP1_RATIO  = 0.65

BOT_TOKEN  = "8624452830:AAEPQLCJ-jMOZzKJp91CUl2zKf1u-sGUZlI"
CHAT_ID    = "6541777069"

STATE = {"chat_id": CHAT_ID, "last_scan": "Başlatılıyor...", "signals_sent": 0}

def send_telegram_msg(chat_id, msg):
    if not BOT_TOKEN or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}).encode("utf-8")
        urllib.request.urlopen(url, data=payload, timeout=10)
    except Exception as e:
        print(f"Telegram hatası: {e}")

def fetch_candles_perp(symbol, interval, limit=100):
    clean_sym = symbol.replace(".P", "")
    try:
        url = f"https://fapi.binance.com/fapi/v1/klines?symbol={clean_sym}&interval={interval}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
        return [{"time": int(d[0]), "open": float(d[1]), "high": float(d[2]), "low": float(d[3]), "close": float(d[4])} for d in raw]
    except Exception:
        bybit_tf = {"15m": "15", "1h": "60", "4h": "240"}.get(interval, "60")
        url = f"https://api.bybit.com/v5/market/kline?category=linear&symbol={clean_sym}&interval={bybit_tf}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        lst = list(reversed(data["result"]["list"]))
        return [{"time": int(d[0]), "open": float(d[1]), "high": float(d[2]), "low": float(d[3]), "close": float(d[4])} for d in lst]

def fmt_p(p):
    if p >= 1000: return f"{p:.2f}"
    if p >= 10:   return f"{p:.3f}"
    return f"{p:.4f}"

def build_live_summary():
    lines = ["☁️ <b>7/24 BULUT PERPETUAL (.P) BEKLEYEN KUTULAR</b>\n━━━━━━━━━━━━━━━━━━"]
    found = 0
    for sym in SYMBOLS:
        for tf in TIMEFRAMES:
            try:
                candles = fetch_candles_perp(sym, tf, 75)
                n = len(candles)
                atr = [0.0] * n
                for i in range(1, n):
                    pc = candles[i-1]["close"]
                    tr = max(candles[i]["high"]-candles[i]["low"], abs(candles[i]["high"]-pc), abs(candles[i]["low"]-pc))
                    atr[i] = tr if i < 14 else (atr[i-1]*13 + tr)/14.0
                cur_p = candles[-1]["close"]
                for i in range(n - 20, n - 1):
                    c, c1, c2 = candles[i], candles[i-1], candles[i-2]
                    body1, range1 = abs(c1["close"]-c1["open"]), c1["high"]-c1["low"]
                    if body1 >= atr[i-1]*1.1 and range1 > 0 and body1/range1 >= 0.52:
                        if c1["close"] > c1["open"] and c["low"] > c2["high"]:
                            mt = (c2["high"] + min(c2["low"], c1["low"])) / 2.0
                            if all(candles[k]["low"] > mt for k in range(i+1, n)):
                                lines.append(f"🟢 <b>{sym}.P [{tf.upper()}] LONG</b> | Giriş: <code>{fmt_p(mt)}</code> <i>(Anlık: {fmt_p(cur_p)})</i>")
                                found += 1
                        elif c1["close"] < c1["open"] and c["high"] < c2["low"]:
                            mt = (max(c2["high"], c1["high"]) + c2["low"]) / 2.0
                            if all(candles[k]["high"] < mt for k in range(i+1, n)):
                                lines.append(f"🔴 <b>{sym}.P [{tf.upper()}] SHORT</b> | Giriş: <code>{fmt_p(mt)}</code> <i>(Anlık: {fmt_p(cur_p)})</i>")
                                found += 1
            except Exception:
                pass
    if found == 0:
        lines.append("Şu an bekleyen taze kutu yok, tarama devam ediyor...")
    lines.append("━━━━━━━━━━━━━━━━━━\n✅ <i>Bilgisayarın kapalı olsa bile bulut sunucu 7/24 nöbette!</i>")
    return "\n".join(lines)

def bot_worker():
    notified_keys = set()
    last_update_id = 0
    last_scan_time = 0
    send_telegram_msg(CHAT_ID, "☁️ <b>7/24 Bulut Sunucun Başarıyla Devreye Girdi!</b>\nArtık bilgisayarını tamamen kapatsan bile sinyaller gelmeye devam edecek.")

    while True:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            for item in data.get("result", []):
                uid = item["update_id"]
                if uid > last_update_id:
                    last_update_id = uid
                msg = item.get("message") or item.get("edited_message") or {}
                cid = str(msg.get("chat", {}).get("id", ""))
                text = (msg.get("text") or "").strip().lower()
                if cid and text in ["/start", "/durum", "/liste", "durum", "merhaba", "selam"]:
                    send_telegram_msg(cid, build_live_summary())
        except Exception:
            pass

        now = time.time()
        if now - last_scan_time >= 30:
            last_scan_time = now
            STATE["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for sym in SYMBOLS:
                for tf in TIMEFRAMES:
                    try:
                        perp_name = f"{sym}.P"
                        candles = fetch_candles_perp(sym, tf, 100)
                        n = len(candles)
                        if n < 30: continue
                        atr = [0.0] * n
                        for i in range(n):
                            c = candles[i]
                            if i == 0: atr[i] = c["high"] - c["low"]
                            else:
                                pc = candles[i-1]["close"]
                                tr = max(c["high"]-c["low"], abs(c["high"]-pc), abs(c["low"]-pc))
                                atr[i] = tr if i < 14 else (atr[i-1]*13 + tr)/14.0

                        setups = []
                        for i in range(20, n - 1):
                            c, c1, c2 = candles[i], candles[i-1], candles[i-2]
                            for s in setups:
                                if s["touched"] or s["invalidated"] or i <= s["created_bar"] + 1: continue
                                if i - s["created_bar"] > 40: s["invalidated"] = True; continue
                                if s["is_bull"] and c["low"] <= s["ob_mt"]:
                                    if c["close"] < s["ob_mt"]: s["invalidated"] = True; continue
                                    s["touched"] = True; s["touch_bar"] = i; s["touch_low"] = c["low"]
                                elif not s["is_bull"] and c["high"] >= s["ob_mt"]:
                                    if c["close"] > s["ob_mt"]: s["invalidated"] = True; continue
                                    s["touched"] = True; s["touch_bar"] = i; s["touch_high"] = c["high"]

                            body1, range1 = abs(c1["close"]-c1["open"]), c1["high"]-c1["low"]
                            if body1 >= atr[i-1]*1.1 and range1 > 0 and body1/range1 >= 0.52:
                                if c1["close"] > c1["open"] and c["low"] > c2["high"] and c1["close"] > c2["high"]:
                                    ob_top, ob_bot = c2["high"], min(c2["low"], c1["low"])
                                    setups.append({"is_bull": True, "created_bar": i, "time": c["time"], "ob_top": ob_top, "ob_bot": ob_bot, "ob_mt": (ob_top+ob_bot)/2, "touched": False, "invalidated": False, "touch_bar": -1})
                                elif c1["close"] < c1["open"] and c["high"] < c2["low"] and c1["close"] < c2["low"]:
                                    ob_top, ob_bot = max(c2["high"], c1["high"]), c2["low"]
                                    setups.append({"is_bull": False, "created_bar": i, "time": c["time"], "ob_top": ob_top, "ob_bot": ob_bot, "ob_mt": (ob_top+ob_bot)/2, "touched": False, "invalidated": False, "touch_bar": -1})

                        for s in setups:
                            if s["touched"] and s["touch_bar"] == n - 2:
                                key = f"TRADE_{perp_name}_{tf}_{s['time']}"
                                if key not in notified_keys:
                                    notified_keys.add(key)
                                    ent = s["ob_mt"]
                                    cur_atr = atr[s["touch_bar"]]
                                    if s["is_bull"]:
                                        sl = min(s["ob_bot"], s["touch_low"]) - cur_atr * 0.30
                                        risk = max(ent - sl, ent * 0.001)
                                        tp1, tp2 = ent + risk * TP1_RATIO, ent + risk * RR_RATIO
                                        direction = "🟢 YENİ LONG İŞLEM AÇILDI"
                                    else:
                                        sl = max(s["ob_top"], s["touch_high"]) + cur_atr * 0.30
                                        risk = max(sl - ent, ent * 0.001)
                                        tp1, tp2 = ent - risk * TP1_RATIO, ent - risk * RR_RATIO
                                        direction = "🔴 YENİ SHORT İŞLEM AÇILDI"
                                    sl_pct = abs(ent - sl) / ent
                                    margin_10x = (RISK_USD / sl_pct if sl_pct > 0 else WALLET_USD) / 10.0
                                    msg = (
                                        f"<b>{direction} [{perp_name} - {tf.upper()}]</b>\n"
                                        f"━━━━━━━━━━━━━━━━━━\n"
                                        f"🎯 <b>Giriş (%50 MT):</b> <code>{fmt_p(ent)}</code>\n"
                                        f"🛡️ <b>TP1 (Stopu Girişe Çek):</b> <code>{fmt_p(tp1)}</code> (+{TP1_RATIO}R)\n"
                                        f"🔥 <b>TP2 (Ana Hedef):</b> <code>{fmt_p(tp2)}</code> (+{RR_RATIO}R)\n"
                                        f"🛑 <b>STOP (SL):</b> <code>{fmt_p(sl)}</code> (-1R)\n"
                                        f"━━━━━━━━━━━━━━━━━━\n"
                                        f"💰 <b>100$ Kasa İçin:</b> <b>{margin_10x:.1f}$ Marjin (10x İzole)</b>"
                                    )
                                    send_telegram_msg(CHAT_ID, msg)
                    except Exception:
                        pass
        time.sleep(2)

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"SMC Cloud Bot Aktif! Son Tarama: {STATE['last_scan']}".encode("utf-8"))
    def log_message(self, format, *args):
        return

if __name__ == "__main__":
    threading.Thread(target=bot_worker, daemon=True).start()
    port = int(os.environ.get("PORT", 8080))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
