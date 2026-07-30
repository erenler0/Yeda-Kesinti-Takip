"""
yedas_scraper.py
------------------
YEDAŞ Planlı Kesinti Verisi Çekme ve Eşleştirme Modülü (Performans Optimize Versiyon)
"""

import random
import re
from datetime import datetime, timedelta
import pandas as pd
import requests

# YEDAŞ Canlı API Endpoint'i
YEDAS_API_URL = "https://www.yedas.com/api/planli-kesinti-harita"

KESINTI_COLUMNS = ["İl", "İlçe", "Mahalle", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]

CITY_MAP = {
    "55": "SAMSUN",
    "52": "ORDU",
    "05": "AMASYA",
    "19": "ÇORUM",
    "57": "SİNOP"
}

def _clean_str_series(series: pd.Series) -> pd.Series:
    """Pandas Serisi üzerindeki Türkçe karakterleri ve boşlukları tek seferde (vektörel) temizler."""
    return (
        series.fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace("ı", "i", regex=False)
        .str.replace("i̇", "i", regex=False)
        .str.replace("ğ", "g", regex=False)
        .str.replace("ü", "u", regex=False)
        .str.replace("ş", "s", regex=False)
        .str.replace("ö", "o", regex=False)
        .str.replace("ç", "c", regex=False)
        .str.replace(" ", "", regex=False)
    )


def _parse_details_time(details_text: str):
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
    """
    10K+ Saha Verisinde Bile Işık Hızında Çalışan Vektörel Eşleştirme Modülü.
    """
    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame(columns=[
            "Saha ID", "İl", "İlçe", "Mahalle",
            "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"
        ])

    s = sahalar_df.copy()
    k = kesintiler_df.copy()

    # 1. Temizlenmiş Eşleşme Anahtarları Üret (Vektörel - Çok Hızlı)
    s["_il_key"] = _clean_str_series(s["İl"])
    s["_mah_key"] = _clean_str_series(s["Mahalle"])

    k["_il_key"] = _clean_str_series(k["İl"])
    k["_mah_key"] = _clean_str_series(k["Mahalle"])

    # 2. Ana Eşleştirme Anahtarı: "İl + Mahalle" (İlçe isim farklılıklarından etkilenmemek için)
    s["_match_key"] = s["_il_key"] + "___" + s["_mah_key"]
    k["_match_key"] = k["_il_key"] + "___" + k["_mah_key"]

    # 3. Pandas Inner Join (Hızlı Hashing Algoritması)
    merged = pd.merge(
        s,
        k[["_match_key", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]],
        on="_match_key",
        how="inner"
    )

    # 4. Gereksiz sütunları temizle ve döndür
    output_cols = ["Saha ID", "İl", "İlçe", "Mahalle", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]
    
    if merged.empty:
        return pd.DataFrame(columns=output_cols)

    return merged[output_cols].drop_duplicates().reset_index(drop=True)


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
