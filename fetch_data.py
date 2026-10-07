#!/usr/bin/env python3
"""Récupère les cours Yahoo Finance pour tous les actifs de assets_v3.json
et écrit data.json (état) + data.js (lu par index.html). Lancé chaque jour par GitHub Actions."""
import json, os, time, datetime, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0"
FX = "EURUSD=X"

def fetch(ticker):
    last = None
    for host in ("query1", "query2"):
        url = ("https://%s.finance.yahoo.com/v8/finance/chart/%s?range=2y&interval=1d&events=history&includeAdjustedClose=true"
               % (host, urllib.parse.quote(ticker)))
        for k in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                q = json.loads(urllib.request.urlopen(req, timeout=20).read())["chart"]["result"][0]
                ind = q["indicators"]
                c = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
                series = [[t, round(p, 6)] for t, p in zip(q.get("timestamp") or [], c) if p is not None]
                if not series: raise ValueError("aucune donnée")
                return series
            except Exception as e:
                last = e; time.sleep(2 * (k + 1))
    raise last

def main():
    cfg = json.load(open(os.path.join(HERE, "assets_v3.json"), encoding="utf-8"))
    tickers = [a["ticker"] for a in cfg["canaries"] + cfg["offensive"]] + [FX]
    try: old = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8")).get("data", {})
    except Exception: old = {}
    def one(t):
        try: return t, {"series": fetch(t)}
        except Exception as e:
            print("ECHEC", t, e)
            return t, old.get(t) or {"error": str(e)}   # on garde les anciens cours si Yahoo échoue
    with ThreadPoolExecutor(max_workers=3) as ex:
        data = dict(ex.map(one, tickers))
    ok = sum(1 for v in data.values() if "series" in v)
    print("%d/%d tickers OK" % (ok, len(tickers)))
    if ok == 0: raise SystemExit("Aucune donnée récupérée : fichiers non modifiés")
    out = {"updated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "config": cfg, "data": data}
    json.dump(out, open(os.path.join(HERE, "data.json"), "w", encoding="utf-8"), separators=(",", ":"))
    open(os.path.join(HERE, "data.js"), "w", encoding="utf-8").write("window.QUOTES=" + json.dumps(out, separators=(",", ":")) + ";")

if __name__ == "__main__": main()
