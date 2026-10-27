#!/usr/bin/env python3
"""Logged-in jumbo.cl actions (orders, cart) through the user's own Chrome session.

Calls Jumbo's web API from inside a jumbo.cl tab of a Chrome started with
--remote-debugging-port, so the site's own session token is used and refreshed.

  jumbo_account.py start                  # open Chrome with the Jumbo profile (login once there)
  jumbo_account.py orders [--pages 3]     # past orders with items
  jumbo_account.py frequent [--pages 3]   # products ranked by how often you buy them
  jumbo_account.py cart                   # current cart with prices and stock
  jumbo_account.py missing [--min 2]      # frequent products not in the cart
  jumbo_account.py set SKU=QTY ...        # set cart quantities (0 removes)
  jumbo_account.py repeat ORDER_ID        # put every item of a past order in the cart
  jumbo_account.py open [/mi-carro]       # show a jumbo.cl page in that Chrome
"""
import argparse, json, os, subprocess, sys, time, urllib.request
from collections import defaultdict

PORT = 9333
PROFILE = os.path.expanduser("~/.jumbo-cl/profile")
CHROME = os.environ.get("JUMBO_CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
BFF = "https://be-reg-groceries-bff-jumbo.ecomm.cencosud.com"
KEYS = {"orders": "be-reg-groceries-jumbo-order-ghti0t739jnfu",
        "cart": "be-reg-groceries-jumbo-cart-rhk68rqi0adn"}
JS = """async ([url, key, method, body]) => {
  const r = await fetch(url, {method, headers: {
    authorization: 'Bearer ' + localStorage.getItem('sessionDataToken'), apikey: key,
    'x-client-platform': 'web', 'x-client-version': '1.3.2', 'Content-Type': 'application/json'},
    body: body ? JSON.stringify(body) : undefined});
  return {status: r.status, body: await r.text()};
}"""


def chrome_up():
    try:
        urllib.request.urlopen(f"http://localhost:{PORT}/json/version", timeout=2)
        return True
    except OSError:
        return False


def start(url="https://www.jumbo.cl/"):
    if chrome_up():
        return
    # Plain Chrome, not Playwright-launched: Google login rejects automated browsers.
    try:
        os.remove(os.path.join(PROFILE, "SingletonLock"))
    except OSError:
        pass
    subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
                      "--no-first-run", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if chrome_up():
            return
        time.sleep(0.5)
    sys.exit("No pude abrir Chrome")


class Jumbo:
    def __enter__(self):
        from playwright.sync_api import sync_playwright
        start()
        self.pw = sync_playwright().start()
        ctx = self.pw.chromium.connect_over_cdp(f"http://localhost:{PORT}").contexts[0]
        self.page = next((p for p in ctx.pages if "jumbo.cl" in p.url), None)
        if not self.page:
            self.page = ctx.new_page()
            self.page.goto("https://www.jumbo.cl/", wait_until="domcontentloaded")
            self.page.wait_for_timeout(3000)
        return self

    def __exit__(self, *a):
        self.pw.stop()  # disconnects only; the user's Chrome stays open

    def call(self, path, svc, method="GET", body=None):
        for attempt in (0, 1):
            r = self.page.evaluate(JS, [BFF + path, KEYS[svc], method, body])
            if r["status"] < 400 or attempt:
                break
            if r["status"] >= 500:  # cart provider fails intermittently; the site retries once too
                self.page.wait_for_timeout(1500)
                continue
            # token lasts ~1h; reloading lets the site refresh it
            self.page.reload(wait_until="domcontentloaded")
            self.page.wait_for_timeout(4000)
        if r["status"] == 401:
            sys.exit("Sesión expirada: inicia sesión en la ventana de Chrome de Jumbo (jumbo_account.py open)")
        if r["status"] >= 400:
            sys.exit(f"{method} {path} -> {r['status']}: {r['body'][:300]}")
        return json.loads(r["body"]) if r["body"] else None

    def orders(self, pages):
        out = []
        for pg in range(1, pages + 1):
            d = self.call(f"/orders?page={pg}&perPage=10", "orders")
            out += d.get("payload") or []
            if pg >= (d.get("pages") or 1):
                break
        return out

    def cart(self, store):
        return self.call(f"/cart?store={store}&simulationTotals=true", "cart")

    def set_items(self, qty_by_sku, store):
        # removing (qty 0) fails unless itemQuantityLimit is sent, as the site does
        items = [{"skuId": str(s), "quantity": int(q), "giftable": False, "isUnitaryEligible": False,
                  "itemQuantityLimit": 12} for s, q in qty_by_sku.items()]
        return self.call("/cart/items?fullCart=true&simulationTotals", "cart", "PATCH", {"items": items, "store": store})


def slim_order(o):
    return {"id": o["id"], "date": o["createdAt"][:10], "status": o["status"], "store": o["store"],
            "total": (o.get("totals") or {}).get("total"),
            "items": [{"sku": i["skuId"], "name": i["name"], "qty": i["quantity"], "price": i["price"],
                       "status": i.get("status")} for i in o.get("items") or []]}


def frequent(orders):
    agg = defaultdict(lambda: {"times": 0, "qty": 0})
    for o in orders:
        if o["status"] in ("CANCELED", "CANCELLED"):
            continue
        for i in o.get("items") or []:
            a = agg[i["skuId"]]
            a["times"] += 1
            a["qty"] += i["quantity"]
            a.setdefault("last_date", o["createdAt"][:10])  # orders come newest first
            a.setdefault("last_price", i["price"])
            a.setdefault("name", i["name"])
    rows = [{"sku": s, "name": a["name"], "times": a["times"], "avg_qty": round(a["qty"] / a["times"], 1),
             "last_date": a["last_date"], "last_price": a["last_price"]} for s, a in agg.items()]
    return sorted(rows, key=lambda r: (-r["times"], r["name"]))


def slim_cart(c):
    return {"items": [{"sku": i["skuId"], "name": i.get("name"), "qty": i["quantity"],
                       "price": (i.get("prices") or {}).get("price"),
                       "total": (i.get("prices") or {}).get("totalPrice"),
                       "status": i.get("status")} for i in c.get("items") or []],
            "totals": c.get("totals")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["start", "orders", "frequent", "cart", "missing", "set", "repeat", "open"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--pages", type=int, default=3, help="10 orders per page")
    ap.add_argument("--min", type=int, default=2, help="missing: bought in at least N orders")
    ap.add_argument("--store", help="store id like jumboclj512 (default: store of your last order)")
    a = ap.parse_args()

    if a.cmd == "start":
        return start()
    if a.cmd == "open":
        start()
        subprocess.run(["curl", "-s", "-X", "PUT", f"http://localhost:{PORT}/json/new?https://www.jumbo.cl"
                        + (a.args[0] if a.args else "/mi-carro")], stdout=subprocess.DEVNULL)
        return

    with Jumbo() as j:
        pages = 1 if a.cmd in ("cart", "set") and a.store else a.pages
        orders = [] if a.store and a.cmd in ("cart", "set") else j.orders(1 if a.cmd in ("cart", "set") else pages)
        store = a.store or (orders[0]["store"] if orders else None)
        if a.cmd in ("cart", "set", "repeat", "missing") and not store:
            sys.exit("Sin pedidos previos: pasa --store (ej. jumboclj512)")

        if a.cmd == "orders":
            out = [slim_order(o) for o in orders]
        elif a.cmd == "frequent":
            out = frequent(orders)
        elif a.cmd == "cart":
            out = slim_cart(j.cart(store))
        elif a.cmd == "missing":
            in_cart = {i["skuId"] for i in j.cart(store).get("items") or []}
            out = [r for r in frequent(orders) if r["times"] >= a.min and r["sku"] not in in_cart]
        elif a.cmd == "set":
            qty = dict(x.split("=", 1) for x in a.args)
            j.set_items(qty, store)
            out = slim_cart(j.cart(store))
        elif a.cmd == "repeat":
            o = next((o for o in j.orders(a.pages) if o["id"] == a.args[0]), None)
            if not o:
                sys.exit(f"No encontré el pedido {a.args[0]} (prueba --pages más alto)")
            have = {i["skuId"]: i["quantity"] for i in j.cart(o["store"]).get("items") or []}
            add = {i["skuId"]: have.get(i["skuId"], 0) + i["quantity"]
                   for i in o.get("items") or [] if i.get("canRepeatPurchase", True)}
            j.set_items(add, o["store"])
            out = slim_cart(j.cart(o["store"]))
        print(json.dumps({"store": store, "result": out} if a.cmd != "orders" else out,
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
