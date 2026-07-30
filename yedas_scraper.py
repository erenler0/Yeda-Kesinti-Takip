"""
yedas_scraper.py
------------------
YEDAŞ Planlı Kesinti Verisi Çekme ve Eşleştirme Modülü (Canlı API Entegreli)
"""

import random
import re
from datetime import datetime, timedelta
import pandas as pd
import requests

# YEDAŞ Canlı API Endpoint'i
YEDAS_API_URL = "https://www.yedas.com/api/planli-kesinti-harita"

# Standart kesinti tablosu sütunları
KESINTI_COLUMNS = ["İl", "İlçe", "Mahalle", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]


def _normalize_text(x: str) -> str:
    """Türkçe karakter/boşluk/büyük-küçük harf farklarını yok sayarak karşılaştırma anahtarı üretir."""
    if x is None:
        return ""
    x = str(x).strip().lower()
    replacements = {"ı": "i", "İ": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
    for src, tgt in replacements.items():
        x = x.replace(src, tgt)
    return x


def _parse_details_time(details_text: str):
    """'details' alanı içerisindeki başlangıç ve bitiş tarihlerini regex ile ayıklar."""
    baslangic = ""
    bitis = ""
    if not details_text:
        return baslangic, bitis

    # Tarih formatlarını yakala (Örn: 09.08.2026 09:15:00)
    times = re.findall(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}(?::\d{2})?", details_text)
    if len(times) >= 2:
        baslangic = times[0]
        bitis = times[1]
    elif len(times) == 1:
        baslangic = times[0]

    return baslangic, bitis


def _fetch_live_data() -> pd.DataFrame:
    """YEDAŞ API'sinden canlı JSON verisini çeker ve DataFrame'e dönüştürür."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.yedas.com/planli-kesinti"
        }
        resp = requests.get(YEDAS_API_URL, headers=headers, timeout=15)
        resp.raise_for_status()

        res_json = resp.json()

        # Veri nesnesi 'result -> data' altında yer alıyor
        data_block = res_json.get("result", {}).get("data", [])
        if not data_block and isinstance(res_json, list):
            data_block = res_json

        rows = []
        for item in data_block:
            title = item.get("title", "")
            details = item.get("details", "")
            baslangic, bitis = _parse_details_time(details)

            addresses = item.get("address", [])
            
            # Eğer adres listesi varsa her adrese göre satır üret veya ilkini esas al
            if addresses:
                for addr in addresses:
                    il = addr.get("city_name") or addr.get("il") or addr.get("id_city") or ""
                    ilce = addr.get("district_name") or addr.get("ilce") or addr.get("id_district") or ""
                    mahalle = addr.get("mah_name") or addr.get("mahalle") or addr.get("id_mah") or ""

                    rows.append({
                        "İl": str(il).strip(),
                        "İlçe": str(ilce).strip(),
                        "Mahalle": str(mahalle).strip(),
                        "Kesinti Başlangıç Saati": baslangic,
                        "Kesinti Bitiş Saati": bitis,
                        "Açıklama/Nedeni": str(title).strip(),
                    })
            else:
                rows.append({
                    "İl": "",
                    "İlçe": "",
                    "Mahalle": "",
                    "Kesinti Başlangıç Saati": baslangic,
                    "Kesinti Bitiş Saati": bitis,
                    "Açıklama/Nedeni": str(title).strip(),
                })

        df = pd.DataFrame(rows, columns=KESINTI_COLUMNS)
        # Tamamen boş satırları ele
        df = df.dropna(how="all")
        return df

    except Exception:
        # Canlı çekilemezse boş döner (Sistem Demo veriye düşer)
        return pd.DataFrame(columns=KESINTI_COLUMNS)


def _generate_demo_data(sahalar_df: pd.DataFrame) -> pd.DataFrame:
    """Canlı veri çekilemediğinde test amaçlı sahte veri üretir."""
    if sahalar_df.empty:
        return pd.DataFrame(columns=KESINTI_COLUMNS)

    nedenler = [
        "Trafo bakımı", "Hat yenileme çalışması", "Şalt sahası bakımı",
        "Direk değişimi", "Enerji nakil hattı bakımı", "Altyapı iyileştirme çalışması",
    ]

    sample_size = min(len(sahalar_df), max(1, len(sahalar_df) // 3))
    sample = sahalar_df.sample(n=sample_size, random_state=None)

    rows = []
    now = datetime.now()
    for _, saha in sample.iterrows():
        gun_offset = random.choice([0, 0, 1, 2, 3, 5, 6])
        baslangic_dt = now.replace(hour=random.choice([8, 9, 10, 13]), minute=0, second=0) + timedelta(days=gun_offset)
        bitis_dt = baslangic_dt + timedelta(hours=random.choice([2, 3, 4, 6]))
        rows.append({
            "İl": saha["İl"],
            "İlçe": saha["İlçe"],
            "Mahalle": saha["Mahalle"],
            "Kesinti Başlangıç Saati": baslangic_dt.strftime("%d.%m.%Y %H:%M"),
            "Kesinti Bitiş Saati": bitis_dt.strftime("%d.%m.%Y %H:%M"),
            "Açıklama/Nedeni": random.choice(nedenler),
        })

    return pd.DataFrame(rows, columns=KESINTI_COLUMNS)


def get_kesintiler(sahalar_df: pd.DataFrame):
    """Canlı veriyi çekmeyi dener, boşsa demo veriye düşer."""
    live_df = _fetch_live_data()
    if not live_df.empty:
        return live_df, False
    demo_df = _generate_demo_data(sahalar_df)
    return demo_df, True


def match_sahalar_with_kesintiler(sahalar_df: pd.DataFrame, kesintiler_df: pd.DataFrame) -> pd.DataFrame:
    """Kayıtlı sahaları YEDAŞ kesinti verisiyle eşleştirir."""
    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame(columns=[
            "Saha ID", "İl", "İlçe", "Mahalle",
            "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"
        ])

    s = sahalar_df.copy()
    k = kesintiler_df.copy()

    s["_key"] = (s["İl"].map(_normalize_text) + "|" + s["İlçe"].map(_normalize_text) + "|" + s["Mahalle"].map(_normalize_text))
    k["_key"] = (k["İl"].map(_normalize_text) + "|" + k["İlçe"].map(_normalize_text) + "|" + k["Mahalle"].map(_normalize_text))

    merged = pd.merge(s, k.drop(columns=["İl", "İlçe", "Mahalle"]), on="_key", how="inner")
    merged = merged.drop(columns=["_key"])

    return merged[["Saha ID", "İl", "İlçe", "Mahalle",
                    "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]]


def filter_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Kesinti tablosunu tarih filtresine göre süzmektedir."""
    if df.empty:
        return df

    days_map = {"Bugün": 0, "3 Günlük": 3, "7 Günlük": 7}
    days = days_map.get(period, 0)

    now = datetime.now()
    start_limit = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_limit = start_limit + timedelta(days=days + 1)

    def _parse_dt(val):
        try:
            return datetime.strptime(str(val), "%d.%m.%Y %H:%M:%S")
        except Exception:
            try:
                return datetime.strptime(str(val), "%d.%m.%Y %H:%M")
            except Exception:
                return None

    df = df.copy()
    df["_baslangic_dt"] = df["Kesinti Başlangıç Saati"].map(_parse_dt)

    valid_dates = df["_baslangic_dt"].notna()
    if valid_dates.any():
        filtered = df[valid_dates & (df["_baslangic_dt"] >= start_limit) & (df["_baslangic_dt"] < end_limit)]
        return filtered.drop(columns=["_baslangic_dt"]).reset_index(drop=True)

    return df.drop(columns=["_baslangic_dt"])
