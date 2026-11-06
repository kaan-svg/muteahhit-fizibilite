"""Elle toplanan ilanlardan (sahibinden, sifir bina) pazar verisi cikarir.

Girdi: data/ilanlar.csv
    mahalle,tip,brut_m2,fiyat_tl,site_havuz,ilan_tarihi
    Mahmutlar,1+1,62,"4.250.000",evet,2026-11-06

Cikti:
  - mahalle bazinda MEDYAN m2 fiyati -> data/pazar.csv (--yaz ile)
  - daire tipine gore medyan brut m2 (daire.py varsayilanlari icin oneri)
  - daire tipine gore m2 fiyat farki (tip_carpani icin oneri)
  - site/havuz olan ve olmayan ilanlarin fiyat farki

Ortalama yerine medyan: tek bir asiri pahali ilan ortalamayi bozar.
Ilan fiyati istenen fiyattir; gercek satis fiyati genelde biraz dusuktur.

Kullanim:
    python -m src.ilanlar                  # ozet tablo
    python -m src.ilanlar --yaz            # pazar.csv'yi gunceller
"""
import argparse
import csv
import re
import statistics
from datetime import date
from pathlib import Path

VERI = Path(__file__).resolve().parent.parent / "data"
ILAN_YOLU = VERI / "ilanlar.csv"
PAZAR_YOLU = VERI / "pazar.csv"
SUTUNLAR = ["mahalle", "tip", "brut_m2", "fiyat_tl", "site_havuz", "ilan_tarihi"]
MIN_ILAN = 5          # bir mahallenin fiyatini guncellemek icin en az bu kadar ilan
AYKIRI_ALT, AYKIRI_UST = 0.5, 2.0   # medyanin yarisindan az / iki katindan fazla m2 fiyati atilir

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _anahtar(mahalle):
    """'Çıkcıllı ' -> 'cikcilli' (pazar.csv ile eslestirmek icin)"""
    return mahalle.strip().translate(_TR).lower()


def _sayi(metin, ad, satir):
    """'4.250.000 TL' -> 4250000, '62 m2' -> 62, '62,5' -> 62.5"""
    s = str(metin).upper().replace("TL", "").replace("M2", "").replace("M²", "").strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):      # binlik ayiricili tamsayi
        s = s.replace(".", "")
    s = s.replace(" ", "").replace(",", ".")
    try:
        x = float(s)
    except ValueError:
        raise ValueError(f"{satir}. satir: {ad} sayi degil: {metin!r}")
    if x <= 0:
        raise ValueError(f"{satir}. satir: {ad} pozitif olmali: {metin!r}")
    return x


def _tip(metin, satir):
    m = re.fullmatch(r"\s*(\d)\s*\+\s*(\d)\s*", str(metin))
    if not m:
        raise ValueError(f"{satir}. satir: tip '1+1' biciminde olmali: {metin!r}")
    return f"{m.group(1)}+{m.group(2)}"


def _metin_oku(yol):
    """Google Sheets UTF-8, Turkce Excel ise cp1254 ve ';' ile kaydeder; ikisini de okur."""
    ham = Path(yol).read_bytes()
    try:
        metin = ham.decode("utf-8-sig")
    except UnicodeDecodeError:
        metin = ham.decode("cp1254")
    ilk_satir = metin.splitlines()[0] if metin else ""
    ayirici = ";" if ilk_satir.count(";") > ilk_satir.count(",") else ","
    return metin, ayirici


def oku(yol=ILAN_YOLU):
    import io
    metin, ayirici = _metin_oku(yol)
    with io.StringIO(metin, newline="") as f:
        okuyucu = csv.DictReader(f, delimiter=ayirici)
        eksik = [s for s in ("mahalle", "tip", "brut_m2", "fiyat_tl") if s not in (okuyucu.fieldnames or [])]
        if eksik:
            raise ValueError(f"CSV'de eksik sutun: {', '.join(eksik)}. Beklenen: {', '.join(SUTUNLAR)}")
        ilanlar = []
        for i, r in enumerate(okuyucu, start=2):   # 1. satir baslik
            if not any((v or "").strip() for v in r.values()):
                continue
            m2 = _sayi(r["brut_m2"], "brut_m2", i)
            fiyat = _sayi(r["fiyat_tl"], "fiyat_tl", i)
            ilanlar.append({
                "mahalle": r["mahalle"].strip(),
                "tip": _tip(r["tip"], i),
                "brut_m2": m2,
                "fiyat_tl": fiyat,
                "m2_fiyat": fiyat / m2,
                "site_havuz": (r.get("site_havuz") or "").strip().lower() in ("evet", "var", "e", "1", "true"),
            })
    return ilanlar


def aykirilari_ayir(ilanlar):
    """Mahalle medyaninin yarisindan ucuz veya iki katindan pahali m2 fiyatli ilanlari ayirir.
    (yazim hatasi, villa, dukkan gibi). (temiz, atilanlar) dondurur."""
    medyan = {}
    for m in {_anahtar(i["mahalle"]) for i in ilanlar}:
        medyan[m] = statistics.median(i["m2_fiyat"] for i in ilanlar if _anahtar(i["mahalle"]) == m)
    temiz, atilan = [], []
    for i in ilanlar:
        oran = i["m2_fiyat"] / medyan[_anahtar(i["mahalle"])]
        (temiz if AYKIRI_ALT <= oran <= AYKIRI_UST else atilan).append(i)
    return temiz, atilan


def _grupla(ilanlar, anahtar):
    gruplar = {}
    for i in ilanlar:
        gruplar.setdefault(anahtar(i), []).append(i)
    return gruplar


def ozet(ilanlar):
    temiz, atilan = aykirilari_ayir(ilanlar)
    genel = statistics.median(i["m2_fiyat"] for i in temiz)

    mahalleler = {}
    for _, grup in sorted(_grupla(temiz, lambda i: _anahtar(i["mahalle"])).items()):
        mahalleler[grup[0]["mahalle"]] = {
            "ilan": len(grup), "m2_fiyat": round(statistics.median(i["m2_fiyat"] for i in grup))}

    tipler = {}
    for tip, grup in sorted(_grupla(temiz, lambda i: i["tip"]).items()):
        # tip carpani: ayni mahalledeki medyana gore oran (mahalle farkini ayiklar)
        oranlar = [i["m2_fiyat"] / mahalleler[_mahalle_adi(mahalleler, i)]["m2_fiyat"] for i in grup]
        tipler[tip] = {"ilan": len(grup), "brut_m2": round(statistics.median(i["brut_m2"] for i in grup)),
                       "tip_carpani": round(statistics.median(oranlar), 2)}

    site = [i["m2_fiyat"] for i in temiz if i["site_havuz"]]
    sitesiz = [i["m2_fiyat"] for i in temiz if not i["site_havuz"]]
    site_farki = (round(statistics.median(site) / statistics.median(sitesiz) - 1, 2)
                  if len(site) >= 3 and len(sitesiz) >= 3 else None)

    return {"toplam": len(ilanlar), "kullanilan": len(temiz), "atilan": atilan,
            "genel_m2_fiyat": round(genel), "mahalleler": mahalleler, "tipler": tipler,
            "site_farki": site_farki}


def _mahalle_adi(mahalleler, ilan):
    k = _anahtar(ilan["mahalle"])
    return next(m for m in mahalleler if _anahtar(m) == k)


def pazar_guncelle(o, yol=PAZAR_YOLU, bugun=None):
    """Yeterli ilani olan mahallelerin fiyatini gunceller, digerlerine dokunmaz.
    Guncellenen mahalle adlarini dondurur."""
    bugun = bugun or date.today().strftime("%Y-%m")
    with open(yol, newline="", encoding="utf-8") as f:
        satirlar = list(csv.DictReader(f))
    mevcut = {_anahtar(r["mahalle"]): r for r in satirlar}
    guncellenen = []
    for ad, v in o["mahalleler"].items():
        if v["ilan"] < MIN_ILAN:
            continue
        yeni = {"mahalle": mevcut.get(_anahtar(ad), {}).get("mahalle", ad.translate(_TR)),
                "m2_fiyat": str(v["m2_fiyat"]),
                "kaynak": f"sahibinden sifir bina medyani ({v['ilan']} ilan)", "tarih": bugun}
        if _anahtar(ad) in mevcut:
            mevcut[_anahtar(ad)].update(yeni)
        else:
            satirlar.append(yeni)
            mevcut[_anahtar(ad)] = yeni
        guncellenen.append(ad)
    with open(yol, "w", newline="", encoding="utf-8") as f:
        yazici = csv.DictWriter(f, fieldnames=["mahalle", "m2_fiyat", "kaynak", "tarih"])
        yazici.writeheader()
        yazici.writerows(satirlar)
    return guncellenen


def rapor(o, eski=None):
    eski = eski or {}
    tl = lambda x: f"{x:,.0f}".replace(",", ".")
    s = [f"{o['toplam']} ilan, {o['kullanilan']} kullanildi, {len(o['atilan'])} aykiri atildi. "
         f"Genel medyan: {tl(o['genel_m2_fiyat'])} TL/m2", "",
         f"{'Mahalle':<12}{'Ilan':>5}{'Medyan TL/m2':>14}{'Eski':>10}{'Fark':>7}"]
    for ad, v in o["mahalleler"].items():
        e = eski.get(_anahtar(ad))
        fark = f"{v['m2_fiyat'] / e - 1:+.0%}" if e else "-"
        not_ = "" if v["ilan"] >= MIN_ILAN else f"  (az ilan, en az {MIN_ILAN} gerekli)"
        s.append(f"{ad:<12}{v['ilan']:>5}{tl(v['m2_fiyat']):>14}{tl(e) if e else '-':>10}{fark:>7}{not_}")
    s += ["", f"{'Tip':<6}{'Ilan':>5}{'Medyan m2':>11}{'Tip carpani':>13}"]
    for tip, v in o["tipler"].items():
        s.append(f"{tip:<6}{v['ilan']:>5}{v['brut_m2']:>11}{v['tip_carpani']:>13}")
    if o["site_farki"] is not None:
        s += ["", f"Site/havuzlu ilanlar m2'de {o['site_farki']:+.0%} farkli."]
    for i in o["atilan"]:
        s.append(f"  atildi: {i['mahalle']} {i['tip']} {i['brut_m2']:.0f} m2, {tl(i['fiyat_tl'])} TL "
                 f"({tl(i['m2_fiyat'])} TL/m2)")
    return "\n".join(s)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dosya", nargs="?", default=ILAN_YOLU)
    ap.add_argument("--yaz", action="store_true", help="pazar.csv'yi guncelle")
    a = ap.parse_args()

    from src.gelir import pazar_yukle
    eski = {_anahtar(m): f for m, f in pazar_yukle().items()}
    o = ozet(oku(a.dosya))
    print(rapor(o, eski))
    if a.yaz:
        print(f"\npazar.csv guncellendi: {', '.join(pazar_guncelle(o)) or 'hicbiri (yeterli ilan yok)'}")
    else:
        print("\npazar.csv'yi guncellemek icin: python -m src.ilanlar --yaz")
