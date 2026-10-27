"""Gradio web arayuzu.

Iki sekme:
  - Hesap: form -> fizibilite tablosu + arsa sahibi payina gore duyarlilik.
    LLM kullanmaz, aninda calisir. Istenirse "Yorumla" ile model aciklar.
  - Sohbet: agent ile konusma; cagrilan araclar ayri bir kutuda gorunur.

Calistirma:
    python -m src.arayuz        ->  http://localhost:7860
"""
from src.agent import SISTEM_MESAJI, calistir
from src.araclar import _arsa_argumanlari, arac_calistir
from src.gelir import pazar_yukle
from src.senaryo import fizibilite

PAY_DEGERLERI = [30, 35, 40, 45, 50, 55]
BAGLANTI_HATASI = (
    "Modele baglanilamadi. Ollama acik mi? Windows'ta Ollama'yi baslatip "
    "WSL'de `curl localhost:11434` ile kontrol et."
)


def mahalleler():
    return [m.title() for m in sorted(pazar_yukle())]


# ---------- Hesap sekmesi ----------

def _arsa(arsa_alani, taks, emsal, mahalle, oran_11, oran_21, oran_31,
          max_kat, pay, ek_gider, m2_fiyat):
    """Form degerlerini arac argumanlarina cevirir. Yuzdeler 0-100 gelir."""
    return {
        "arsa_alani": arsa_alani, "taks": taks, "emsal": emsal, "mahalle": mahalle,
        "oran_1_1": oran_11 / 100, "oran_2_1": oran_21 / 100, "oran_3_1": oran_31 / 100,
        "max_kat": max_kat or None, "arsa_sahibi_payi": pay / 100,
        "ek_gider_orani": ek_gider / 100, "m2_fiyat": m2_fiyat or None,
    }


def _yuzde(x):
    return f"%{x}".replace(".", ",")


def _tl(milyon):
    return f"{milyon:,.2f} M TL".replace(",", "X").replace(".", ",").replace("X", ".")


def hesapla(*form):
    """(ozet markdown, duyarlilik markdown) dondurur."""
    arsa = _arsa(*form)
    s = arac_calistir("fizibilite_hesapla", arsa)
    if "hata" in s:
        return f"**Hata:** {s['hata']}", ""

    daireler = ", ".join(f"{a} adet {t}" for t, a in s["daireler"].items())
    durum = "✅ Kârlı" if s["kar_milyon_tl"] > 0 else "❌ Zararlı"
    ozet = "\n".join([
        f"### {durum}: {_tl(s['kar_milyon_tl'])} (marj {_yuzde(s['kar_marji_yuzde'])})",
        "",
        "| Kalem | Değer |", "|---|---|",
        f"| Kat sayısı | {s['kat_sayisi']} |",
        f"| İnşaat alanı | {s['insaat_alani_m2']} m² |",
        f"| Daireler | {daireler} |",
        f"| Satış fiyatı | {s['m2_fiyat_tl']:,} TL/m² |".replace(",", "."),
        f"| Brüt satış geliri | {_tl(s['brut_gelir_milyon_tl'])} |",
        f"| Arsa sahibine kalan | {_tl(s['arsa_sahibine_kalan_milyon_tl'])} |",
        f"| Müteahhit geliri | {_tl(s['muteahhit_geliri_milyon_tl'])} |",
        f"| Toplam gider | {_tl(s['toplam_gider_milyon_tl'])} |",
        f"| **Kâr** | **{_tl(s['kar_milyon_tl'])}** |",
        "",
        "_Tahmini değerlerdir. Fiyatlar ilan ortalaması, maliyet Bakanlık birim fiyatıdır; "
        "emsal dışı alanlar (balkon, otopark) henüz hesaba katılmıyor._",
    ])

    d = arac_calistir("duyarlilik_analizi", {"arsa": arsa, "parametre": "arsa_sahibi_payi",
                                             "degerler": [p / 100 for p in PAY_DEGERLERI]})
    simdiki = round(arsa["arsa_sahibi_payi"] * 100)
    satirlar = ["#### Arsa sahibi payına göre kâr", "", "| Pay | Kâr | Marj |", "|---|---|---|"]
    for r in d["sonuclar"]:
        pay = round(r["arsa_sahibi_payi"] * 100)
        isaret = " ← şu an" if pay == simdiki else ""
        satirlar.append(f"| %{pay}{isaret} | {_tl(r['kar_milyon_tl'])} | {_yuzde(r['kar_marji_yuzde'])} |")
    return ozet, "\n".join(satirlar)


def yorumla(*form, acikla=None):
    """Formdaki senaryoyu modele yorumlatir."""
    if acikla is None:
        from src.llm import acikla
    try:
        sonuc = fizibilite(**_arsa_argumanlari(_arsa(*form)))
    except (ValueError, KeyError) as e:
        return f"**Hata:** {e}"
    try:
        return acikla(sonuc)
    except Exception:
        return BAGLANTI_HATASI


# ---------- Sohbet sekmesi ----------

def _metin(icerik):
    """Gradio mesaj icerigi str veya [{'type': 'text', 'text': ...}] olabilir."""
    if isinstance(icerik, str):
        return icerik
    if isinstance(icerik, dict):
        return icerik.get("text", "")
    if isinstance(icerik, (list, tuple)):
        return "\n".join(_metin(p) for p in icerik)
    return str(icerik or "")


def gecmisten_mesajlar(gecmis):
    """Gradio gecmisini agent mesajlarina cevirir. Arac gunlugu kutulari atlanir."""
    mesajlar = [{"role": "system", "content": SISTEM_MESAJI}]
    for m in gecmis or []:
        if (m.get("metadata") or {}).get("title"):
            continue
        if m.get("role") in ("user", "assistant"):
            mesajlar.append({"role": m["role"], "content": _metin(m.get("content"))})
    return mesajlar


def sohbet(mesaj, gecmis, calistir_fn=calistir):
    import gradio as gr

    mesajlar = gecmisten_mesajlar(gecmis) + [{"role": "user", "content": mesaj}]
    gunluk = []
    yaz = lambda satir: gunluk.append(satir.strip()) if satir.strip().startswith(("->", "!")) else None
    try:
        cevap = calistir_fn(mesajlar, gunluk=yaz)
    except Exception:
        return BAGLANTI_HATASI
    if not gunluk:
        return cevap
    return [
        gr.ChatMessage(content="\n".join(gunluk), metadata={"title": "🔧 Çağrılan araçlar"}),
        gr.ChatMessage(content=cevap),
    ]


# ---------- Arayuz ----------

ORNEKLER = [
    "Mahmutlar'da 1000 m2 arsam var, TAKS 0.30, emsal 1.50. Arsa sahibine %45 veriyorum, ek gider %25. Kârlı mı?",
    "Aynı arsada pay %40 ve %50 olsa kâr nasıl değişir?",
    "Balkonlar emsale dahil mi?",
    "Hangi mahallelerin fiyat verisi var?",
]


def arayuz():
    import gradio as gr

    with gr.Blocks(title="Müteahhit Fizibilite Asistanı") as demo:
        gr.Markdown("# 🏗️ Müteahhit Fizibilite Asistanı\nAlanya için arsa fizibilitesi. "
                    "**Bilgi amaçlıdır, yatırım tavsiyesi değildir.**")
        with gr.Tab("Hesap"):
            with gr.Row():
                with gr.Column():
                    arsa_alani = gr.Number(1000, label="Arsa alanı (m²)")
                    with gr.Row():
                        taks = gr.Number(0.30, label="TAKS", step=0.05)
                        emsal = gr.Number(1.50, label="Emsal", step=0.05)
                        max_kat = gr.Number(0, label="Kat sınırı (0 = yok)", precision=0)
                    mahalle = gr.Dropdown(mahalleler(), value="Mahmutlar", label="Mahalle")
                    m2_fiyat = gr.Number(0, label="m² satış fiyatı TL (0 = mahalle ortalaması)")
                    gr.Markdown("**Daire karışımı (alan payı %)**")
                    with gr.Row():
                        o11 = gr.Slider(0, 100, 50, step=5, label="1+1")
                        o21 = gr.Slider(0, 100, 50, step=5, label="2+1")
                        o31 = gr.Slider(0, 100, 0, step=5, label="3+1")
                    pay = gr.Slider(0, 70, 45, step=1, label="Arsa sahibi payı % (kat karşılığı)")
                    ek = gr.Slider(0, 60, 25, step=1, label="Ek giderler % (KDV, ruhsat, pazarlama)")
                    with gr.Row():
                        hesapla_btn = gr.Button("Hesapla", variant="primary")
                        yorum_btn = gr.Button("Model yorumlasın")
                with gr.Column():
                    ozet = gr.Markdown()
                    duyarlilik = gr.Markdown()
                    yorum = gr.Markdown()
            girdiler = [arsa_alani, taks, emsal, mahalle, o11, o21, o31, max_kat, pay, ek, m2_fiyat]
            hesapla_btn.click(hesapla, girdiler, [ozet, duyarlilik])
            yorum_btn.click(yorumla, girdiler, yorum)
            demo.load(hesapla, girdiler, [ozet, duyarlilik])
        with gr.Tab("Sohbet"):
            gr.ChatInterface(sohbet, examples=ORNEKLER, run_examples_on_click=True,
                             chatbot=gr.Chatbot(height=520, label="Asistan"),
                             textbox=gr.Textbox(placeholder="Sorunu yaz: arsa bilgileri veya imar sorusu...",
                                                submit_btn=True))
    return demo


if __name__ == "__main__":
    import gradio as gr
    arayuz().launch(theme=gr.themes.Soft())
