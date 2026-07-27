#!/usr/bin/env python3
"""
DATEV EXTF v700 Buchungsstapel export — replicates the format found in the
original Lovable app's index-n87V4MEw.js bundle (function producing the
"EXTF" header row and the `bFe` column-header array).

Usage: python3 datev_export.py 2026-05-26 2026-07-05 [wolt,ubereats,lieferando]
Writes datev_export_<from>_<to>.csv (DATEV wants CP1252/Windows-1252, ";"-sep,
values quoted, decimal comma).
"""
import json, sys, csv, io

COLUMNS = [
    "Umsatz (ohne Soll/Haben-Kz)","Soll/Haben-Kennzeichen","WKZ Umsatz","Kurs","Basis-Umsatz",
    "WKZ Basis-Umsatz","Konto","Gegenkonto (ohne BU-Schlüssel)","BU-Schlüssel","Belegdatum",
    "Belegfeld 1","Belegfeld 2","Skonto","Buchungstext","Postensperre","Diverse Adressnummer",
    "Geschäftspartnerbank","Sachverhalt","Zinssperre","Beleglink",
    "Beleginfo - Art 1","Beleginfo - Inhalt 1","Beleginfo - Art 2","Beleginfo - Inhalt 2",
    "Beleginfo - Art 3","Beleginfo - Inhalt 3","Beleginfo - Art 4","Beleginfo - Inhalt 4",
    "Beleginfo - Art 5","Beleginfo - Inhalt 5","Beleginfo - Art 6","Beleginfo - Inhalt 6",
    "Beleginfo - Art 7","Beleginfo - Inhalt 7","Beleginfo - Art 8","Beleginfo - Inhalt 8",
]

# SKR04-ish mapping (confirm final account numbers with Herr Steuer before filing)
KONTO_ERLOSE_7 = "8300"      # Erlöse 7% USt
KONTO_KASSE = "1600"         # Kasse (Restaurant)
KONTO_FREMDLEISTUNG_19 = "5900"  # Fremdleistungen / Provisionen 19% VSt
KONTO_FREMDLEISTUNG_94 = "5906"  # Fremdleistungen innergem. Reverse-Charge (BU 94)

BU94_PLATFORMS = {"Wolt", "Uber Eats"}  # per manifest.vat_and_bu_schluessel_rules

def de_amount(x):
    return f"{x:.2f}".replace(".", ",")

def datev_date(iso_date):
    # DATEV Belegdatum wants ddmm (no year) inside the Buchungssatz per EXTF spec
    y, m, d = iso_date.split("-")
    return f"{d}{m}"

def extf_header(date_from, date_to, consultant_no="0", client_no="0"):
    y = date_from[:4]
    wj_start = f"{y}0101"
    return ["EXTF", 700, 21, "Buchungsstapel", 7,
            date_from.replace("-", ""), "", "RE", "COT-Dashboard", "",
            consultant_no, client_no, wj_start, KONTO_KASSE, date_from.replace("-", ""),
            date_to.replace("-", ""), f"COT {date_from}-{date_to}", "", 1, 0, 0, "EUR",
            "", "", "", "", ""]

def build_rows(entries):
    rows = []
    for e in entries:
        if e["type"] != "Einnahme":
            continue  # Geldtransit offset entries net out Kassenbestand; not separately DATEV-booked
        if e["platform"].startswith("SumUp"):
            # Split into two postings: 7% and 19% portions, per the Steuerübersicht on the Tagesabschlussbericht
            if e.get("vat7_gross"):
                rows.append({
                    "Umsatz (ohne Soll/Haben-Kz)": de_amount(e["vat7_gross"]), "Soll/Haben-Kennzeichen": "S",
                    "Konto": KONTO_KASSE, "Gegenkonto (ohne BU-Schlüssel)": KONTO_ERLOSE_7, "BU-Schlüssel": "",
                    "Belegdatum": datev_date(e["date"]), "Belegfeld 1": e["platform"][:12],
                    "Buchungstext": (e["note"] + " (7%)")[:60]})
            if e.get("vat19_gross"):
                rows.append({
                    "Umsatz (ohne Soll/Haben-Kz)": de_amount(e["vat19_gross"]), "Soll/Haben-Kennzeichen": "S",
                    "Konto": KONTO_KASSE, "Gegenkonto (ohne BU-Schlüssel)": "8400", "BU-Schlüssel": "",
                    "Belegdatum": datev_date(e["date"]), "Belegfeld 1": e["platform"][:12],
                    "Buchungstext": (e["note"] + " (19%)")[:60]})
            continue
        rows.append({
            "Umsatz (ohne Soll/Haben-Kz)": de_amount(e["gross"]),
            "Soll/Haben-Kennzeichen": "S",
            "Konto": KONTO_KASSE,
            "Gegenkonto (ohne BU-Schlüssel)": KONTO_ERLOSE_7,
            "BU-Schlüssel": "",
            "Belegdatum": datev_date(e["date"]),
            "Belegfeld 1": e["platform"][:12],
            "Buchungstext": e["note"][:60],
        })
    return rows

def write_csv(path, header, rows):
    with io.open(path, "w", newline="", encoding="cp1252", errors="replace") as f:
        w = csv.writer(f, delimiter=";", quoting=csv.QUOTE_ALL)
        w.writerow(header)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow([r.get(c, "") for c in COLUMNS])

def main():
    date_from = sys.argv[1] if len(sys.argv) > 1 else "2026-05-26"
    date_to = sys.argv[2] if len(sys.argv) > 2 else "2026-07-05"
    with open("kassenbuch.json") as f:
        books = json.load(f)
    entries = [e for e in books["restaurant"]["entries"] if date_from <= e["date"] <= date_to]
    rows = build_rows(entries)
    header = extf_header(date_from, date_to)
    out = f"datev_export_{date_from}_{date_to}.csv"
    write_csv(out, header, rows)
    print(f"Wrote {out} — {len(rows)} Buchungssätze")

if __name__ == "__main__":
    main()
