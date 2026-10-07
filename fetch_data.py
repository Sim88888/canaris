#!/usr/bin/env python3
"""Récupère les cours Yahoo Finance des actifs de assets_v3.json -> data.json + data.js (lu par index.html).
Lancé par GitHub Actions plusieurs fois par jour : ne retélécharge que les cours manquants ou vieux de plus de 20 h.
Yahoo limite les requêtes par adresse IP (erreur 429) : requêtes espacées, attentes, abandon rapide si l'IP est bloquée."""
import json, os, time, random, datetime, urllib.request, urllib.parse, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
FX = "EURUSD=X"
MAX_AGE = 20 * 3600
UAS = [
 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
 "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
 "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
]

class Blocked(Exception): pass

def fetch(ticker):
    last = None
    for attempt in range(4):
        host = ("query1", "query2")[attempt % 2]
        url = ("https://%s.finance.yahoo.com/v8/finance/chart/%s?range=2y&interval=1d&events=history&includeAdjustedClose=true"
               % (host, urllib.parse.quote(ticker)))
        req = urllib.request.Request(url, headers={
            "User-Agent": random.choice(UAS), "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8", "Referer": "https://finance.yahoo.com/"})
        try:
            q = json.loads(urllib.request.urlopen(req, timeout=25).read())["chart"]["result"][0]
            ind = q["indicators"]
            c = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
            series = [[t, round(p, 6)] for t, p in zip(q.get("timestamp") or [], c) if p is not None]
            if not series: raise ValueError("aucune donnée")
            return series
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                time.sleep(20 + 20 * attempt)      # on laisse Yahoo se calmer
            elif e.code == 404:
                raise ValueError("ticker inconnu (404)")
            else:
                time.sleep(3)
        except Exception as e:
            last = e; time.sleep(3)
    if isinstance(last, urllib.error.HTTPError) and last.code == 429:
        raise Blocked(str(last))
    raise last

def main():
    cfg = json.load(open(os.path.join(HERE, "assets_v3.json"), encoding="utf-8"))
    tickers = [a["ticker"] for a in cfg["canaries"] + cfg["offensive"]] + [FX]
    try: data = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8")).get("data", {})
    except Exception: data = {}
    data = {t: v for t, v in data.items() if t in tickers}
    now = time.time()
    todo = [t for t in tickers if "series" not in data.get(t, {}) or now - data[t].get("ts", 0) > MAX_AGE]
    random.shuffle(todo)
    print("%d ticker(s) à mettre à jour sur %d" % (len(todo), len(tickers)))
    got, blocked_streak = 0, 0
    for t in todo:
        try:
            data[t] = {"series": fetch(t), "ts": int(time.time())}
            got += 1; blocked_streak = 0
            print("OK    ", t)
        except Blocked as e:
            blocked_streak += 1
            print("BLOQUÉ", t, e)
            if blocked_streak >= 2:
                print("Yahoo refuse cette adresse IP : abandon (nouvelle tentative au prochain passage)."); break
        except Exception as e:
            print("ECHEC ", t, e)
            data.setdefault(t, {"error": str(e)})
        time.sleep(random.uniform(1.5, 3.5))
    have = sum(1 for v in data.values() if "series" in v)
    print("%d/%d tickers disponibles (%d mis à jour)" % (have, len(tickers), got))
    if got:
        last = max(v.get("ts", 0) for v in data.values())
        out = {"updated": datetime.datetime.fromtimestamp(last, datetime.timezone.utc).isoformat(timespec="seconds"),
               "config": cfg, "data": data}
        json.dump(out, open(os.path.join(HERE, "data.json"), "w", encoding="utf-8"), separators=(",", ":"))
        open(os.path.join(HERE, "data.js"), "w", encoding="utf-8").write("window.QUOTES=" + json.dumps(out, separators=(",", ":")) + ";")
    elif have == 0:
        raise SystemExit("Aucun cours disponible pour l'instant.")

if __name__ == "__main__": main()
