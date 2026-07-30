"""
yedas_scraper.py
------------------
YEDAŞ Planlı Kesinti Verisi Çekme ve Eşleştirme Modülü (Performans & Esnek Eşleştirme Yapılandırılmış)
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

def _normalize_text(x: str) -> str:
    """Tekil metin temizliği için yedek yardımcı fonksiyon."""
    if x is None:
        return ""
    x = str(x).strip().lower()
    replacements = {"ı": "i", "i̇": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
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
    10K+ Saha Verisinde Bile Donmayan Ultra Hızlı ve Esnek Eşleştirme Modülü.
    """
    output_cols = ["Saha ID", "İl", "İlçe", "Mahalle", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]

    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame(columns=output_cols)

    s = sahalar_df.copy()
    k = kesintiler_df.copy()

    # 1. Temizlenmiş Eşleşme Anahtarları Üret (Vektörel - Anında hesaplanır)
    s["_il_key"] = _clean_str_series(s["İl"])
    s["_ilce_key"] = _clean_str_series(s["İlçe"])
    s["_mah_key"] = _clean_str_series(s["Mahalle"])

    k["_il_key"] = _clean_str_series(k["İl"])
    k["_ilce_key"] = _clean_str_series(k["İlçe"])
    k["_mah_key"] = _clean_str_series(k["Mahalle"])

    # 2. Aşama: Tam Eşleşenleri Pandas Merge İle Işık Hızında Yakala
    s["_match_key"] = s["_il_key"] + "___" + s["_mah_key"]
    k["_match_key"] = k["_il_key"] + "___" + k["_mah_key"]

    direct_matches = pd.merge(
        s,
        k[["_match_key", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]],
        on="_match_key",
        how="inner"
    )

    matched_saha_ids = set(direct_matches["Saha ID"]) if not direct_matches.empty else set()

    # 3. Aşama: Tam Eşleşmeyenler İçin Sadece Aynı İl İçinde Esnek (İç İçe Metin) Arama Yap
    # (Tüm tabloyu çarpmadığı için 10k sahada bile çökmeyi engeller)
    matched_rows = []
    
    unmatched_s = s[~s["Saha ID"].isin(matched_saha_ids)]

    if not unmatched_s.empty:
        for il_key, s_group in unmatched_s.groupby("_il_key"):
            k_group = k[k["_il_key"] == il_key]
            if k_group.empty:
                continue

            for _, s_row in s_group.iterrows():
                s_mah = s_row["_mah_key"]
                s_ilce = s_row["_ilce_key"]

                if not s_mah:
                    continue

                # Kısmi mahalle eşleşmesi arama
                mask_mah = k_group["_mah_key"].str.contains(s_mah, regex=False) | k_group["_mah_key"].apply(lambda x: x in s_mah if x else False)
                
                # İlçe kontrolü (İlçe adı boş veya eşleşiyorsa)
                if s_ilce:
                    mask_ilce = (k_group["_ilce_key"] == "") | k_group["_ilce_key"].str.contains(s_ilce, regex=False) | k_group["_ilce_key"].apply(lambda x: x in s_ilce if x else False)
                    k_matches = k_group[mask_mah & mask_ilce]
                else:
                    k_matches = k_group[mask_mah]

                if not k_matches.empty:
                    for _, k_row in k_matches.iterrows():
                        matched_rows.append({
                            "Saha ID": s_row["Saha ID"],
                            "İl": s_row["İl"],
                            "İlçe": s_row["İlçe"],
                            "Mahalle": s_row["Mahalle"],
                            "Kesinti Başlangıç Saati": k_row["Kesinti Başlangıç Saati"],
                            "Kesinti Bitiş Saati": k_row["Kesinti Bitiş Saati"],
                            "Açıklama/Nedeni": k_row["Açıklama/Nedeni"]
                        })

    # Sonuçları Birleştir
    all_dfs = []
    if not direct_matches.empty:
        all_dfs.append(direct_matches[output_cols])
    if matched_rows:
        all_dfs.append(pd.DataFrame(matched_rows)[output_cols])

    if not all_dfs:
        return pd.DataFrame(columns=output_cols)

    final_df = pd.concat(all_dfs, ignore_index=True)
    return final_df.drop_duplicates().reset_index(drop=True)


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
