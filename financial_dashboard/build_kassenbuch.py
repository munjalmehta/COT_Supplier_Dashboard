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

def sumup_entries(days, book, terminal_label):
    """SumUp card payments are dine-in revenue actually received as cash-equivalent
    (Kassenbestand tracks it directly per the Tagesabschlussbericht Bargeldbestand),
    so unlike delivery platforms this is a straight Einnahme — no Geldtransit offset,
    since SumUp settlement already reconciles against the till in these reports."""
    entries = []
    for d in days:
        entries.append({"date": d["date"], "book": book, "platform": f"SumUp {terminal_label}", "type": "Einnahme",
                         "gross": d["gross"], "net": d["net"], "vat": d["vat"], "vat_rate": "7/19 split",
                         "vat7_gross": d.get("vat7_gross",0), "vat19_gross": d.get("vat19_gross",0),
                         "tips": d.get("tips",0), "cash_component": d.get("cash",0),
                         "note": f"Tagesabschlussbericht {d['date']} — SumUp {terminal_label}",
                         "source": f"Tagesabschlussbericht-{d['date']}.pdf"})
    return entries

def main():
    wolt = load("wolt_periods.json")
    ubereats = load("ubereats_periods.json")
    lieferando = load("lieferando_periods.json")
    sumup_restaurant = load("sumup_restaurant_daily.json")
    sumup_foodtruck = load("sumup_foodtruck_daily.json")

    restaurant_entries = (wolt_entries(wolt) + ubereats_entries(ubereats) + lieferando_entries(lieferando)
                          + sumup_entries(sumup_restaurant, "restaurant", "Restaurant"))
    restaurant_entries.sort(key=lambda e: e["date"])

    foodtruck_entries = sumup_entries(sumup_foodtruck, "foodtruck", "Foodtruck")
    foodtruck_entries.sort(key=lambda e: e["date"])

    books = {
        "restaurant": {"entries": restaurant_entries, "note": ""},
        "foodtruck": {"entries": foodtruck_entries,
                       "note": "Foodtruck terminal (MCKQLK39) sales during Tollwood period — separate Tollwood Kasse not yet distinguished, see manifest"},
        "tollwood": {"entries": [], "note": "Not yet distinguished from Foodtruck terminal data — see manifest.coverage.tollwood"}
    }

    with open("kassenbuch.json", "w") as f:
        json.dump(books, f, indent=2, ensure_ascii=False)

    total_einnahme = sum(e["gross"] for e in restaurant_entries if e["type"] == "Einnahme")
    print(f"Wrote kassenbuch.json — {len(restaurant_entries)} restaurant + {len(foodtruck_entries)} foodtruck entries, restaurant book Einnahme total €{total_einnahme:,.2f}")

if __name__ == "__main__":
    main()
