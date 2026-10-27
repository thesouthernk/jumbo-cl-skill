#!/usr/bin/env python3
"""Search jumbo.cl and print products with prices as JSON.

Usage: jumbo_search.py "leche entera" [--pages N] [--sort price|unit|discount]
"""
import argparse, json, re, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def fetch(query, page):
    url = "https://www.jumbo.cl/busqueda?" + urllib.parse.urlencode({"ft": query, "page": page})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "es-CL"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def rsc_payload(html):
    # Next.js streams page data as self.__next_f.push([1,"<json-escaped string>"])
    chunks = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', html)
    return "".join(json.loads(c) for c in chunks)


def parse(html):
    data, dec, out, seen = rsc_payload(html), json.JSONDecoder(), [], set()
    for m in re.finditer(r'"product":\{"productId"', data):
        try:
            p, _ = dec.raw_decode(data, m.start() + len('"product":'))
        except json.JSONDecodeError:
            continue
        for it in p.get("items") or []:
            sku = it.get("skuId")
            if not sku or sku in seen:
                continue
            seen.add(sku)
            price, lst = it.get("price"), it.get("listPrice")
            # promo names look like "TCENCO OFERTA 11990 - LPM: ..."; keep only the head
            promos = [x["name"].split(" - ")[0] for x in it.get("promotions") or [] if isinstance(x, dict) and x.get("name")]
            card = [int(m.group(1)) for x in promos if (m := re.match(r"TCENCO\D*(\d+)", x))]
            out.append({
                "name": it.get("name"),
                "brand": p.get("brand"),
                "sku": sku,
                "price": price,
                "list_price": lst if lst and price and lst > price else None,
                "discount_pct": round(100 * (lst - price) / lst) if lst and price and lst > price else 0,
                "unit_price": it.get("ppumPrice"),
                "unit": it.get("ppumMeasurementUnit"),
                "in_stock": it.get("stock"),
                "card_price": min(card) if card else None,  # Tarjeta Cencosud
                "promos": promos,
                "url": f"https://www.jumbo.cl/{p.get('slug')}/p",
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--pages", type=int, default=1, help="40 products per page")
    ap.add_argument("--sort", choices=["price", "unit", "discount"])
    a = ap.parse_args()
    items = []
    for pg in range(1, a.pages + 1):
        got = parse(fetch(a.query, pg))
        if not got:
            break
        items += got
    key = {"price": lambda x: x["price"] or 1e12,
           "unit": lambda x: x["unit_price"] or 1e12,
           "discount": lambda x: -x["discount_pct"]}.get(a.sort)
    if key:
        items.sort(key=key)
    if not items:
        sys.exit(f"Sin resultados para '{a.query}' (o cambió el HTML de jumbo.cl)")
    json.dump(items, sys.stdout, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
