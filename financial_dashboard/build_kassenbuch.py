#!/usr/bin/env python3
"""
Derives Kassenbuch entries from platform revenue JSON.

COT workflow (per memory/manifest): gross delivery/card revenue is booked as
cash-equivalent Einnahme (income), VAT-split, then immediately offset by a
Geldtransit [Platform] Ausgabe of the same amount, since the money never
actually sits in the physical Kassenbestand — it settles via bank payout.
This keeps VAT reporting correct while leaving Kassenbestand unaffected.

Restaurant, Foodtruck and Tollwood are separate Kassenbücher. Wolt/UberEats/
Lieferando revenue in this seed is restaurant-channel only.
"""
import json

BOOK = "restaurant"

def load(name):
    with open(name) as f:
        return json.load(f)

def wolt_entries(periods):
    entries = []
    for p in periods:
        gross = round(p["goods_gross"] + p["deliveries_gross"] + p["service_gross"]
                       + p["discounts_gross"] + p["purchase_corr_gross"] + p["deductions_gross"], 2)
        vat = round(p["goods_vat"] + p["deliveries_vat"] + p["service_vat"]
                    + p["discounts_vat"] + p["purchase_corr_vat"] + p["deductions_vat"], 2)
        net = round(gross - vat, 2)
        entries.append({"date": p["period_to"], "book": BOOK, "platform": "Wolt", "type": "Einnahme",
                         "gross": gross, "net": net, "vat": vat, "vat_rate": 7,
                         "note": f"Wolt Umsatz {p['period_from']}–{p['period_to']} (Rechnung {p['invoice']})",
                         "source": p["source"]})
        entries.append({"date": p["period_to"], "book": BOOK, "platform": "Wolt", "type": "Geldtransit",
                         "gross": -gross, "net": -net, "vat": -vat, "vat_rate": 7,
                         "note": f"Geldtransit Wolt {p['period_from']}–{p['period_to']}",
                         "source": p["source"]})
    return entries

def ubereats_entries(periods):
    entries = []
    for p in periods:
        gross = p["gross_after_discount"]
        vat = round(gross * 7 / 107, 2)
        net = round(gross - vat, 2)
        entries.append({"date": p["period_to"], "book": BOOK, "platform": "Uber Eats", "type": "Einnahme",
                         "gross": gross, "net": net, "vat": vat, "vat_rate": 7,
                         "note": f"Uber Eats Umsatz {p['period_from']}–{p['period_to']} ({p['orders']} Bestellungen)",
                         "source": p["source"]})
        entries.append({"date": p["period_to"], "book": BOOK, "platform": "Uber Eats", "type": "Geldtransit",
                         "gross": -gross, "net": -net, "vat": -vat, "vat_rate": 7,
                         "note": f"Geldtransit UberEats {p['period_from']}–{p['period_to']}",
                         "source": p["source"]})
    return entries

def lieferando_entries(periods):
    entries = []
    for p in periods:
        gross = p["period_total_revenue"]
        vat = round(gross * 7 / 107, 2)
        net = round(gross - vat, 2)
        entries.append({"date": p["period_to"], "book": BOOK, "platform": "Lieferando", "type": "Einnahme",
                         "gross": gross, "net": net, "vat": vat, "vat_rate": 7,
                         "note": f"Lieferando Umsatz {p['period_from']}–{p['period_to']} (Rechnung {p['invoice']})",
                         "source": p["source"]})
        entries.append({"date": p["period_to"], "book": BOOK, "platform": "Lieferando", "type": "Geldtransit",
                         "gross": -gross, "net": -net, "vat": -vat, "vat_rate": 7,
                         "note": f"Geldtransit Lieferando {p['period_from']}–{p['period_to']}",
                         "source": p["source"]})
    return entries

def main():
    wolt = load("wolt_periods.json")
    ubereats = load("ubereats_periods.json")
    lieferando = load("lieferando_periods.json")

    entries = wolt_entries(wolt) + ubereats_entries(ubereats) + lieferando_entries(lieferando)
    entries.sort(key=lambda e: e["date"])

    books = {
        "restaurant": {"entries": entries,
                        "note": "SumUp Einnahme/Geldtransit entries pending — see manifest.coverage.sumup"},
        "foodtruck": {"entries": [], "note": "No data seeded yet — SumUp Foodtruck pending parse"},
        "tollwood": {"entries": [], "note": "No data seeded yet — Tollwood season ended 19.07.2026, SumUp pending parse"}
    }

    with open("kassenbuch.json", "w") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)

    total_einnahme = sum(e["gross"] for e in entries if e["type"] == "Einnahme")
    print(f"Wrote kassenbuch.json — {len(entries)} entries, restaurant book Einnahme total €{total_einnahme:,.2f}")

if __name__ == "__main__":
    main()
