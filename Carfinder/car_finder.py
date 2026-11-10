#!/usr/bin/env python3
"""
car_finder.py - dealer car-listing agent.

Pulls new and certified pre-owned dealer listings from AutoTrader.com and CarGurus
(through Apify actors), keeps the ones inside your budget / model years / radius,
merges duplicates by VIN, and writes a sorted list with location, model, price
and a direct link to each listing. New cars are capped on MSRP when the listing
has one, otherwise on price. CarGurus has no certified filter, so it supplies new cars only.

Setup (once):
    export APIFY_TOKEN=apify_api_xxx      # Apify Console > Settings > API & Integrations

Run:
    python3 car_finder.py                      # defaults: $40,000, 95113, 100 mi, 2023-2027
    python3 car_finder.py --budget 25000
    python3 car_finder.py --budget 40000 --zip 94538 --radius 50 --max-per-source 500
    python3 car_finder.py --serve              # opens the page with a working Run button

Outputs cars.csv and cars.html (clickable links) in the current folder.
Uses only the Python standard library.
"""
import argparse
import csv
import datetime
import html
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_BUDGET = 40000
KEEP_CONDITIONS = ("New", "Certified")
COST_PER_LISTING = 0.003 * 2 + 0.0008  # AutoTrader new + certified, CarGurus new (Apify free tier)
API ="https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items?clean=true&format=json"
AUTOTRADER = "caffein.dev~autotrader-com-actor"
CARGURUS = "fortuitous_pirate~cargurus-scraper"
AUTOTRADER_RADII = [10, 25, 50, 75, 100, 200, 300, 400, 500]


def run_actor(actor, payload, token, timeout=330):
    req = urllib.request.Request(
        API.format(actor=actor),
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def autotrader_input(a, listing_type):
    radius = next((r for r in AUTOTRADER_RADII if r >= a.radius), 500)
    return {
        "keyword": a.keyword, "zip": a.zip, "searchRadius": str(radius),
        "maxPrice": a.budget, "startYear": a.year_min, "endYear": a.year_max,
        "listingType": listing_type,
        "sellerType": "d", "maxItems": a.max_per_source, "sortBy": "relevance",
    }


def cargurus_input(a):
    p = {
        "country": "US", "zip": a.zip, "searchRadius": a.radius, "condition": "NEW",
        "maxPrice": a.budget, "minYear": a.year_min, "maxYear": a.year_max,
        "sellerType": "DEALER", "sortType": "BEST_MATCH", "maxItems": a.max_per_source,
    }
    if a.keyword:
        p["searchQueries"] = [a.keyword]
    return p


def _num(v):
    try:
        f = float(v)
        return int(f) if f.is_integer() else round(f, 1)
    except (TypeError, ValueError):
        return None


def norm_autotrader(r):
    city = ", ".join(x for x in (r.get("sellerCity"), r.get("sellerState")) if x)
    return {
        "source": "AutoTrader", "year": r.get("year"), "make": r.get("make"),
        "model": r.get("model"), "trim": r.get("trim") or "",
        "price": _num(r.get("salePrice") or r.get("displayPrice")),
        "msrp": _num(r.get("msrp")), "mileage": _num(r.get("mileage")),
        "condition": (r.get("listingType") or "").title(),
        "deal": r.get("dealIndicator") or "", "dealer": r.get("sellerName") or "",
        "location": city, "distance": _num(r.get("sellerDistance")),
        "vin": r.get("vin") or "", "link": r.get("url") or "",
    }


def norm_cargurus(r):
    return {
        "source": "CarGurus", "year": r.get("year"), "make": r.get("make"),
        "model": r.get("model"), "trim": r.get("trim") or "",
        "price": _num(r.get("price")), "msrp": None, "mileage": _num(r.get("mileage")),
        "condition": "New" if r.get("isNew") else (r.get("condition") or "").title(),
        "deal": (r.get("dealRating") or "").replace("_PRICE", "").title(),
        "dealer": (r.get("sellerName") or "").strip(),
        "location": r.get("sellerCity") or "", "distance": _num(r.get("distance")),
        "vin": r.get("vin") or "", "link": r.get("listingUrl") or r.get("detailUrl") or "",
    }


def select(cars, budget, year_min, year_max, radius):
    """Apply the filters again locally, merge duplicate VINs (cheapest wins), sort by price."""
    best = {}
    for c in cars:
        if c["condition"] not in KEEP_CONDITIONS:
            continue
        cap_on = c["msrp"] if c["condition"] == "New" and c["msrp"] else c["price"]
        if c["price"] is None or c["price"] <= 0 or cap_on > budget or not c["link"]:
            continue
        if not c["year"] or not (year_min <= int(c["year"]) <= year_max):
            continue
        if c["distance"] is not None and c["distance"] > radius:
            continue
        key = c["vin"] or c["link"]
        if key not in best or c["price"] < best[key]["price"]:
            c["msrp"] = c["msrp"] or (best[key]["msrp"] if key in best else None)
            best[key] = c
        else:
            best[key]["msrp"] = best[key]["msrp"] or c["msrp"]
    return sorted(best.values(), key=lambda c: (c["price"], c["distance"] or 0))


COLS = ["year", "make", "model", "trim", "price", "msrp", "mileage", "condition", "deal",
        "dealer", "location", "distance", "source", "vin", "link"]


def write_csv(cars, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(cars)


# One filter per table column, in column order. Kept out of the page f-string so braces stay single.
FILTER_JS = """<script>
(() => {
  const kinds = ["multi", "text", "range", "range", "range", "select", "select", "text", "text", "range", "select"];
  const table = document.querySelector("table"), rows = [...table.tBodies[0].rows];
  const count = document.getElementById("count"), bar = table.tHead.insertRow(), filters = [], labels = [];
  const box = (type, hint) => {
    const el = document.createElement("input");
    el.type = type; el.placeholder = hint;
    return el;
  };
  kinds.forEach((kind, col) => {
    const cell = bar.appendChild(document.createElement("th"));
    const text = r => r.cells[col].textContent.trim();
    if (kind === "multi") {
      const menu = cell.appendChild(document.createElement("details"));
      menu.className = "multi";
      const summary = menu.appendChild(document.createElement("summary"));
      const list = menu.appendChild(document.createElement("div"));
      const totals = {};
      rows.forEach(r => { totals[text(r)] = (totals[text(r)] || 0) + 1; });
      const boxes = Object.keys(totals).sort().map(v => {
        const item = list.appendChild(document.createElement("label")), el = box("checkbox", "");
        el.value = v;
        item.append(el, ` ${v || "(blank)"} (${totals[v]})`);
        return el;
      });
      const picked = () => boxes.filter(b => b.checked).map(b => b.value);
      filters.push(r => !picked().length || picked().includes(text(r)));
      labels.push(() => { summary.textContent = picked().length ? `${picked().length} selected` : "All"; });
      document.addEventListener("click", ev => { if (!menu.contains(ev.target)) menu.open = false; });
    } else if (kind === "text") {
      const el = cell.appendChild(box("search", "Filter"));
      filters.push(r => el.value.toLowerCase().split(/\\s+/).every(w => text(r).toLowerCase().includes(w)));
    } else if (kind === "range") {
      const wrap = cell.appendChild(document.createElement("div"));
      wrap.className = "range";
      const lo = wrap.appendChild(box("number", "Min")), hi = wrap.appendChild(box("number", "Max"));
      filters.push(r => {
        const v = parseFloat(text(r).replace(/[^0-9.]/g, ""));
        return (lo.value === "" || v >= +lo.value) && (hi.value === "" || v <= +hi.value);
      });
    } else {
      const el = cell.appendChild(document.createElement("select"));
      el.add(new Option("All", "*"));
      [...new Set(rows.map(text))].sort().forEach(v => el.add(new Option(v || "(blank)", v)));
      filters.push(r => el.value === "*" || text(r) === el.value);
    }
  });
  const apply = () => {
    let shown = 0;
    rows.forEach(r => { r.hidden = !filters.every(f => f(r)); shown += !r.hidden; });
    count.textContent = `Showing ${shown} of ${rows.length}`;
    labels.forEach(update => update());
  };
  bar.addEventListener("input", apply);
  document.getElementById("clear").onclick = () => {
    bar.querySelectorAll("input:not([type=checkbox])").forEach(el => { el.value = ""; });
    bar.querySelectorAll("input[type=checkbox]").forEach(el => { el.checked = false; });
    bar.querySelectorAll("select").forEach(el => { el.value = "*"; });
    apply();
  };
  apply();
})();
</script>"""

RUN_JS = """<script>
(() => {
  const run = document.getElementById("run"), status = document.getElementById("status");
  if (location.protocol === "file:") {
    run.disabled = true;
    status.textContent = "To enable Run, start the page with: python3 car_finder.py --serve";
    return;
  }
  let watching = false;
  const poll = async () => {
    let s;
    try {
      s = await (await fetch("/status")).json();
    } catch (err) {
      run.disabled = false;
      status.textContent = "The car_finder server isn't running.";
      return;
    }
    run.disabled = s.running;
    if (s.running) {
      watching = true;
      status.textContent = `Fetching latest data... ${s.elapsed}s (can take several minutes)`;
      setTimeout(poll, 3000);
    } else if (s.error) {
      status.textContent = `Run failed: ${s.error}`;
    } else if (watching) {
      location.reload();
    } else {
      status.textContent = s.warning;
    }
  };
  run.onclick = async () => {
    if (!confirm(`Fetch the latest listings? This uses about $${run.dataset.cost} of Apify credit.`)) return;
    run.disabled = true;
    await fetch("/refresh", { method: "POST", headers: { "X-Car-Finder": "run" } });
    poll();
  };
  poll();
})();
</script>"""


def write_html(cars, path, a):
    e = html.escape
    fetched = datetime.datetime.now().strftime("%b %d, %Y %I:%M %p")
    cost = a.max_per_source * COST_PER_LISTING
    rows = []
    for c in cars:
        msrp = f"${c['msrp']:,.0f}" if c["msrp"] is not None else ""
        miles = f"{c['mileage']:,.0f}" if c["mileage"] is not None else ""
        dist = f"{c['distance']:.1f} mi" if c["distance"] is not None else ""
        rows.append(
            f"<tr><td>{e(str(c['make']))}</td><td>{e(str(c['year']))} {e(str(c['model']))} {e(c['trim'])}</td>"
            f"<td class=n>${c['price']:,.0f}</td><td class=n>{msrp}</td><td class=n>{miles}</td><td>{e(c['condition'])}</td>"
            f"<td>{e(c['deal'])}</td><td>{e(c['dealer'])}</td><td>{e(c['location'])}</td>"
            f"<td class=n>{dist}</td><td><a href=\"{e(c['link'], quote=True)}\" target=_blank>"
            f"{e(c['source'])}</a></td></tr>"
        )
    page = f"""<!doctype html><meta charset=utf-8><title>Cars under ${a.budget:,}</title>
<style>body{{font:14px system-ui;margin:24px}}table{{border-collapse:collapse;width:100%}}
th,td{{padding:6px 10px;border-bottom:1px solid #ddd;text-align:left}}.n{{text-align:right}}
thead{{position:sticky;top:0;background:#fff}}th input,th select{{width:100%;min-width:64px;box-sizing:border-box;font:inherit;font-weight:400}}
.range{{display:flex;gap:4px}}#clear,#run,#status{{margin-left:8px}}.multi{{position:relative;font-weight:400;min-width:90px}}
.multi summary{{cursor:pointer}}.multi div{{position:absolute;z-index:2;max-height:280px;overflow:auto;background:#fff;border:1px solid #ccc;padding:6px 10px}}
.multi label{{display:block;white-space:nowrap}}.multi input{{width:auto;min-width:0}}</style>
<h2>{len(cars)} new &amp; certified dealer cars up to ${a.budget:,} &middot; {a.year_min}-{a.year_max} &middot;
within {a.radius} mi of {e(a.zip)}</h2>
<p><span id=count></span><button id=clear>Clear filters</button><button id=run data-cost="{cost:.2f}">Run: get latest data</button>
<span id=status></span> &middot; Data from {fetched}</p>
<table><thead><tr><th>Brand<th>Car<th>Price<th>MSRP<th>Miles<th>Condition<th>Deal<th>Dealer<th>Location<th>Distance<th>Link</tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{FILTER_JS}
{RUN_JS}"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)


def refresh(a, token):
    """Fetch every source and rewrite the output files. Existing files are kept if nothing matches."""
    cars, warnings = [], []
    for name, actor, payload, norm in (
        ("AutoTrader new", AUTOTRADER, autotrader_input(a, "NEW"), norm_autotrader),
        ("AutoTrader certified", AUTOTRADER, autotrader_input(a, "CERTIFIED"), norm_autotrader),
        ("CarGurus new", CARGURUS, cargurus_input(a), norm_cargurus),
    ):
        try:
            items = run_actor(actor, payload, token)
            print(f"{name}: {len(items)} listings fetched", file=sys.stderr)
            cars += [norm(r) for r in items]
        except (urllib.error.URLError, TimeoutError, ValueError) as err:
            warnings.append(f"{name} failed ({err})")
            print(f"{warnings[-1]} - continuing with the other sources", file=sys.stderr)

    cars = select(cars, a.budget, a.year_min, a.year_max, a.radius)
    if not cars:
        raise RuntimeError("; ".join(warnings) or "No listings matched. Try a higher --budget or --max-per-source.")
    write_csv(cars, a.out + ".csv")
    write_html(cars, a.out + ".html", a)
    return cars, warnings


def serve(a, token):
    """Serve the page on this machine only; its Run button re-runs refresh()."""
    host = f"127.0.0.1:{a.port}"
    page = a.out + ".html"
    state = {"running": False, "started": 0, "error": "", "warning": ""}
    lock = threading.Lock()
    if not os.path.exists(page):
        write_html([], page, a)

    def work():
        try:
            _, warnings = refresh(a, token)
            state.update(error="", warning="; ".join(warnings))
        except Exception as err:
            state.update(error=str(err), warning="")
        finally:
            state["running"] = False

    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.headers.get("Host") != host:
                self.reply(403, b"{}")
            elif self.path == "/":
                with open(page, "rb") as f:
                    self.reply(200, f.read(), "text/html; charset=utf-8")
            elif self.path == "/status":
                elapsed = int(time.time() - state["started"]) if state["running"] else 0
                self.reply(200, json.dumps({**state, "elapsed": elapsed}).encode())
            else:
                self.reply(404, b"{}")

        def do_POST(self):
            # The custom header stops other websites from triggering paid runs through the browser.
            if self.headers.get("Host") != host or self.headers.get("X-Car-Finder") != "run" or self.path != "/refresh":
                self.reply(403, b"{}")
                return
            with lock:
                if state["running"]:
                    self.reply(409, b"{}")
                    return
                state.update(running=True, started=time.time(), error="", warning="")
            threading.Thread(target=work, daemon=True).start()
            self.reply(202, b"{}")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    print(f"Open http://{host}/  (Ctrl+C to stop)", file=sys.stderr)
    if not a.no_open:
        webbrowser.open(f"http://{host}/")
    server.serve_forever()


def main():
    p = argparse.ArgumentParser(description="Find dealer cars near you within a budget.")
    p.add_argument("--budget", type=int, default=int(os.environ.get("CAR_BUDGET", DEFAULT_BUDGET)),
                   help=f"max price in USD (default {DEFAULT_BUDGET}, or $CAR_BUDGET)")
    p.add_argument("--zip", default="95113", help="search centre ZIP (default 95113, San Jose)")
    p.add_argument("--radius", type=int, default=100, help="miles (default 100)")
    p.add_argument("--year-min", type=int, default=2023)
    p.add_argument("--year-max", type=int, default=2027)
    p.add_argument("--keyword", default="", help="optional make/model, e.g. 'Honda Civic'")
    p.add_argument("--max-per-source", type=int, default=300,
                   help="listings to pull per site; more = fuller list, higher Apify cost")
    p.add_argument("--out", default="cars", help="output file prefix (default 'cars')")
    p.add_argument("--serve", action="store_true", help="serve the page locally with a working Run button")
    p.add_argument("--port", type=int, default=8765, help="port for --serve (default 8765)")
    p.add_argument("--no-open", action="store_true", help="with --serve, don't open a browser")
    a = p.parse_args()

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("Set APIFY_TOKEN first (Apify Console > Settings > API & Integrations).")

    if a.serve:
        serve(a, token)
        return

    try:
        cars, _ = refresh(a, token)
    except RuntimeError as err:
        sys.exit(str(err))
    for c in cars:
        print(f"${c['price']:>7,.0f}  {c['year']} {c['make']} {c['model']} {c['trim']}".ljust(58)
              + f"{c['location'][:22]:<23}{c['link']}")
    print(f"\n{len(cars)} cars -> {a.out}.csv, {a.out}.html", file=sys.stderr)


if __name__ == "__main__":
    main()
