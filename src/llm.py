"""Yerel LLM (Ollama) ile fizibilite sonucunu aciklama.

Kural: hesaplari model YAPMAZ. Rakamlar senaryo.py'den gelir, model sadece
yorumlar. Bu yuzden prompt'a hazir rakamlari verip yeni hesap yapmamasini
soyluyoruz.

Calistirmak icin Ollama acik olmali ve model indirilmis olmali:
    ollama pull qwen3:8b
    python -m src.llm
"""
import os

VARSAYILAN_MODEL = os.environ.get("FIZIBILITE_MODEL", "qwen3:8b")

SISTEM_MESAJI = (
    "Sen Alanya'da calisan kucuk muteahhitlere yardim eden bir fizibilite asistanisin. "
    "Sana hesaplanmis sonuclar verilecek. Kurallar:\n"
    "1. Yeni hesap yapma, rakam uydurma. Sadece verilen rakamlari kullan.\n"
    "2. Turkce, kisa ve sade yaz (en fazla 6-8 cumle).\n"
    "3. Projenin karli olup olmadigini, karin neye en cok bagli oldugunu ve "
    "hangi varsayimlarin kontrol edilmesi gerektigini soyle.\n"
    "4. Yatirim tavsiyesi verme; sonuclarin tahmini oldugunu belirt."
)


def _tl(tutar):
    """12345678 -> '12,3 milyon TL'"""
    return f"{tutar / 1e6:.1f} milyon TL".replace(".", ",")


def sonuc_metni(s):
    """fizibilite() ciktisini modelin okuyacagi duz metne cevirir."""
    daireler = ", ".join(f"{adet} adet {tip}" for tip, adet in s["daireler"].items() if adet)
    marj = f"%{s['kar_marji'] * 100:.0f}" if s["kar_marji"] is not None else "hesaplanamadi"
    return "\n".join([
        f"Senaryo: {s['ad']}",
        f"Kat sayisi: {s['kat_sayisi']}, insaat alani: {s['insaat_alani']:.0f} m2, yapi sinifi: {s['sinif']}",
        f"Daireler: {daireler} (artan alan {s['artan_alan']:.0f} m2)",
        f"Satis fiyati: {s['m2_fiyat']:,.0f} TL/m2".replace(",", "."),
        f"Brut satis geliri: {_tl(s['brut_gelir'])}",
        f"Arsa sahibine kalan: {_tl(s['arsa_sahibine_kalan'])}",
        f"Muteahhit geliri: {_tl(s['musteahhit_geliri'])}",
        f"Insaat maliyeti: {_tl(s['insaat_maliyeti'])}, ek giderler: {_tl(s['ek_gider'])}",
        f"Toplam gider: {_tl(s['toplam_gider'])}",
        f"Kar: {_tl(s['kar'])}, kar marji: {marj}",
    ])


def mesajlar(s):
    return [
        {"role": "system", "content": SISTEM_MESAJI},
        {"role": "user", "content": "Bu sonucu yorumla:\n\n" + sonuc_metni(s)},
    ]


def acikla(s, model=VARSAYILAN_MODEL, istemci=None):
    """Sonucu modele gonderir, aciklama metnini dondurur.

    istemci: test icin sahte bir istemci verilebilir; verilmezse ollama kullanilir.
    """
    if istemci is None:
        import ollama
        istemci = ollama
    yanit = istemci.chat(model=model, messages=mesajlar(s))
    return yanit["message"]["content"].strip()


if __name__ == "__main__":
    from src.senaryo import fizibilite

    sonuc = fizibilite(
        arsa_alani=1000, taks=0.30, emsal=1.50, mahalle="Mahmutlar",
        oranlar={"1+1": 0.5, "2+1": 0.5}, arsa_sahibi_payi=0.45,
        ek_gider_orani=0.25, ad="Mahmutlar 50/50",
    )
    print(sonuc_metni(sonuc))
    print("\n--- Model yorumu ---\n")
    print(acikla(sonuc))
