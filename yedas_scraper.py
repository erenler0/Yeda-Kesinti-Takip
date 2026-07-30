"""
yedas_scraper.py
------------------
YEDAŞ Planlı Kesinti Verisi Çekme ve Eşleştirme Modülü (Canlı API Entegreli - ID Dönüştürmeli)
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

# YEDAŞ Şehir Kodu Haritası (İl bazlı)
CITY_MAP = {
    "55": "SAMSUN",
    "52": "ORDU",
    "05": "AMASYA",
    "19": "ÇORUM",
    "57": "SİNOP"
}

def _normalize_text(x: str) -> str:
    """Türkçe karakter/boşluk/büyük-küçük harf farklarını yok sayarak karşılaştırma anahtarı üretir."""
    if x is None:
        return ""
    x = str(x).strip().lower()
    replacements = {"ı": "i", "İ": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
    for src, tgt in replacements.items():
        x = x.replace(src, tgt)
    return x.replace(" ", "")


def _parse_details_time(details_text: str):
    """'details' alanı içerisindeki başlangıç ve bitiş tarihlerini ayıklar."""
    baslangic = ""
    bitis = ""
    if not details_text:
        return baslangic, bitis

    times = re.findall(r"\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}(?::\d{2})?", details_text)
    if len(times) >= 2:
        baslangic = times[0]
        bitis = times[1]
    elif len(times) == 1:
        baslangic = times[0]

    return baslangic, bitis


def _fetch_live_data() -> pd.DataFrame:
    """YEDAŞ API'sinden canlı JSON verisini çeker ve okunaklı hale getirir."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.yedas.com/planli-kesinti"
        }
        resp = requests.get(YEDAS_API_URL, headers=headers, timeout=15)
        resp.raise_for_status()

        res_json = resp.json()
        data_block = res_json.get("result", {}).get("data", [])
        if not data_block and isinstance(res_json, list):
            data_block = res_json

        rows = []
        for item in data_block:
            title = item.get("title", "")
            details = item.get("details", "")
            baslangic, bitis = _parse_details_time(details)
            addresses = item.get("address", [])
            
            if addresses:
                for addr in addresses:
                    # İl kodunu şehir adına çevir (örn: 55 -> SAMSUN)
                    city_id = str(addr.get("id_city", "")).strip().zfill(2)
                    il_name = addr.get("city_name") or addr.get("il") or CITY_MAP.get(city_id, city_id)

                    ilce_name = addr.get("district_name") or addr.get("ilce") or addr.get("id_district") or ""
                    mah_name = addr.get("mah_name") or addr.get("mahalle") or addr.get("id_mah") or ""

                    rows.append({
                        "İl": str(il_name).strip(),
                        "İlçe": str(ilce_name).strip(),
                        "Mahalle": str(mah_name).strip(),
                        "Kesinti Başlangıç Saati": baslangic,
                        "Kesinti Bitiş Saati": bitis,
                        "Açıklama/Nedeni": str(title).strip(),
                    })

        df = pd.DataFrame(rows, columns=KESINTI_COLUMNS)
        return df.dropna(how="all")

    except Exception:
        return pd.DataFrame(columns=KESINTI_COLUMNS)


def match_sahalar_with_kesintiler(sahalar_df: pd.DataFrame, kesintiler_df: pd.DataFrame) -> pd.DataFrame:
    """Kayıtlı sahaları YEDAŞ kesinti verisiyle esnek eşleştirir."""
    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame(columns=[
            "Saha ID", "İl", "İlçe", "Mahalle",
            "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"
        ])

    matched_rows = []

    # Her kayıtlı saha için kesinti listesinde esnek arama yap
    for _, saha in sahalar_df.iterrows():
        s_il = _normalize_text(saha["İl"])
        s_ilce = _normalize_text(saha["İlçe"])
        s_mah = _normalize_text(saha["Mahalle"])

        for _, kesinti in kesintiler_df.iterrows():
            k_il = _normalize_text(kesinti["İl"])
            k_ilce = _normalize_text(kesinti["İlçe"])
            k_mah = _normalize_text(kesinti["Mahalle"])

            # 1. İl eşleşiyorsa
            # 2. İlçe ya isim olarak eşleşiyorsa ya da kesintideki ilce ID'si var ama mahalle tutuyorsa
            # 3. Mahalle ismi eşleşiyorsa veya kesinti metninde mahalle adı geçiyorsa
            il_match = (s_il == k_il) or (s_il in k_il) or (k_il in s_il)
            
            # İlçe ve mahalle için esnek kontrol
            ilce_match = (not s_ilce) or (s_ilce == k_ilce) or (s_ilce in k_ilce) or (k_ilce in s_ilce)
            mah_match = (not s_mah) or (s_mah == k_mah) or (s_mah in k_mah) or (k_mah in s_mah)

            if il_match and ilce_match and mah_match:
                matched_rows.append({
                    "Saha ID": saha["Saha ID"],
                    "İl": saha["İl"],
                    "İlçe": saha["İlçe"],
                    "Mahalle": saha["Mahalle"],
                    "Kesinti Başlangıç Saati": kesinti["Kesinti Başlangıç Saati"],
                    "Kesinti Bitiş Saati": kesinti["Kesinti Bitiş Saati"],
                    "Açıklama/Nedeni": kesinti["Açıklama/Nedeni"]
                })

    res_df = pd.DataFrame(matched_rows)
    if not res_df.empty:
        return res_df.drop_duplicates().reset_index(drop=True)
    
    return pd.DataFrame(columns=[
        "Saha ID", "İl", "İlçe", "Mahalle",
        "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"
    ])


def _generate_demo_data(sahalar_df: pd.DataFrame) -> pd.DataFrame:
    if sahalar_df.empty:
        return pd.DataFrame(columns=KESINTI_COLUMNS)
    nedenler = ["Trafo bakımı", "Hat yenileme çalışması", "Direk değişimi"]
    sample_size = min(len(sahalar_df), max(1, len(sahalar_df) // 3))
    sample = sahalar_df.sample(n=sample_size, random_state=None)
    rows = []
    now = datetime.now()
    for _, saha in sample.iterrows():
        baslangic_dt = now.replace(hour=9, minute=0)
        bitis_dt = baslangic_dt + timedelta(hours=4)
        rows.append({
            "İl": saha["İl"], "İlçe": saha["İlçe"], "Mahalle": saha["Mahalle"],
            "Kesinti Başlangıç Saati": baslangic_dt.strftime("%d.%m.%Y %H:%M"),
            "Kesinti Bitiş Saati": bitis_dt.strftime("%d.%m.%Y %H:%M"),
            "Açıklama/Nedeni": random.choice(nedenler),
        })
    return pd.DataFrame(rows, columns=KESINTI_COLUMNS)


def get_kesintiler(sahalar_df: pd.DataFrame):
    live_df = _fetch_live_data()
    if not live_df.empty:
        return live_df, False
    demo_df = _generate_demo_data(sahalar_df)
    return demo_df, True


def filter_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
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
