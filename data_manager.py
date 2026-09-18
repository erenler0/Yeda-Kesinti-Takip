"""
data_manager.py
----------------
YEDAŞ Planlı Kesinti Takip Uygulaması - Otomatik Adres Bulucu & Saha Yönetimi
"""

import os
import io
import time
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

SAHA_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahalar.csv")
COLUMNS = ["Saha ID", "Latitude", "Longitude", "İl", "İlçe", "Mahalle"]

# Nominatim (OpenStreetMap) Adres Çözücü Başlatma
geolocator = Nominatim(user_agent="yedas_gsm_tracker")


def _clean_text(x) -> str:
    if pd.isna(x) or x is None:
        return ""
    return str(x).strip()


def get_address_from_coords(lat: str, lon: str) -> tuple:
    """Koordinatlardan İl, İlçe ve Mahalle bilgisini otomatik çeker."""
    try:
        if not lat or not lon:
            return "", "", ""
        
        # Koordinatı sorgula
        location = geolocator.reverse((lat, lon), timeout=5, language="tr")
        if not location:
            return "", "", ""

        address = location.raw.get("address", {})
        
        # Türkiye adres yapısına göre ayrıştırma
        il = address.get("province") or address.get("state") or address.get("city", "")
        ilce = address.get("town") or address.get("district") or address.get("county") or address.get("suburb", "")
        mahalle = address.get("neighbourhood") or address.get("quarter") or address.get("village") or address.get("suburb", "")

        return _clean_text(il), _clean_text(ilce), _clean_text(mahalle)
    except (GeocoderTimedOut, GeocoderServiceError, Exception):
        return "", "", ""


def enrich_missing_addresses(df: pd.DataFrame) -> pd.DataFrame:
    """İl/İlçe/Mahalle bilgisi boş olan sahaların koordinatlarından adreslerini tamamlar."""
    if df.empty:
        return df

    updated = False
    for idx, row in df.iterrows():
        # Eğer İl veya İlçe bilgisi boşsa ve Koordinatlar varsa adres sorgula
        if (not _clean_text(row.get("İl")) or not _clean_text(row.get("İlçe"))) and _clean_text(row.get("Latitude")) and _clean_text(row.get("Longitude")):
            il, ilce, mahalle = get_address_from_coords(row["Latitude"], row["Longitude"])
            
            if il:
                df.at[idx, "İl"] = il
            if ilce:
                df.at[idx, "İlçe"] = ilce
            if mahalle:
                df.at[idx, "Mahalle"] = mahalle
            
            updated = True
            time.sleep(0.5)  # API hız limitine takılmamak için hafif bekleme

    return df


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    # KML/Açıklama içerisinden SITE_NO ayıklama
    if "Açıklama" in df.columns or "Description" in df.columns:
        desc_col = "Açıklama" if "Açıklama" in df.columns else "Description"
        site_ids = df[desc_col].astype(str).str.extract(r'SITE_NO=\s*(\d+)')
        if 0 in site_ids.columns and not site_ids[0].isnull().all():
            df["Saha ID"] = site_ids[0]

    # Sütun İsimlerini Eşleme
    rename_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower()
        if c_clean in ["saha id", "site_no", "site no", "saha_id", "id", "kodu"]:
            rename_map[col] = "Saha ID"
        elif c_clean in ["latitude", "lat", "enlem", "y"]:
            rename_map[col] = "Latitude"
        elif c_clean in ["longitude", "long", "lng", "boylam", "x"]:
            rename_map[col] = "Longitude"
        elif c_clean in ["il", "sehir", "şehir"]:
            rename_map[col] = "İl"
        elif c_clean in ["ilce", "ilçe"]:
            rename_map[col] = "İlçe"
        elif c_clean in ["mahalle", "mah"]:
            rename_map[col] = "Mahalle"

    df = df.rename(columns=rename_map)

    if "Saha ID" not in df.columns or df["Saha ID"].isnull().all():
        df["Saha ID"] = df.iloc[:, 0]

    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS].copy()

    for col in COLUMNS:
        df[col] = df[col].apply(_clean_text)

    df = df[df["Saha ID"] != ""]
    return df.reset_index(drop=True)


def load_sahalar() -> pd.DataFrame:
    if not os.path.exists(SAHA_CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(SAHA_CSV_PATH, dtype=str)
        return _normalize_df(df)
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def save_sahalar(df: pd.DataFrame) -> None:
    df = _normalize_df(df)
    df = df.drop_duplicates(subset=["Saha ID"], keep="last")
    df.to_csv(SAHA_CSV_PATH, index=False, encoding="utf-8-sig")


def bulk_upload(file_or_df, mode: str = "replace") -> pd.DataFrame:
    """Excel veya CSV dosyasını yükler, koordinatlardan adresleri doldurur ve kaydeder."""
    if isinstance(file_or_df, pd.DataFrame):
        new_df = file_or_df
    else:
        file_name = getattr(file_or_df, "name", "").lower()
        if file_name.endswith(('.xlsx', '.xls')):
            new_df = pd.read_excel(file_or_df, dtype=str)
        else:
            bytes_data = file_or_df.getvalue()
            try:
                content = bytes_data.decode("utf-8-sig")
            except Exception:
                content = bytes_data.decode("latin5")
            sep = ";" if ";" in content.split("\n")[0] else ","
            new_df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)

    normalized_df = _normalize_df(new_df)
    
    # Adresleri koordinattan otomatik tamamlama
    normalized_df = enrich_missing_addresses(normalized_df)

    if mode == "replace":
        final_df = normalized_df
    else:
        current_df = load_sahalar()
        final_df = pd.concat([current_df, normalized_df], ignore_index=True)

    save_sahalar(final_df)
    return final_df


def add_or_update_saha(saha_id: str, il: str, ilce: str, mahalle: str, lat: str = "", lon: str = ""):
    current_df = load_sahalar()
    
    # Manuel girilen adreste eksik varsa koordinattan bulmayı dene
    if (not il or not ilce) and lat and lon:
        auto_il, auto_ilce, auto_mah = get_address_from_coords(lat, lon)
        il = il or auto_il
        ilce = ilce or auto_ilce
        mahalle = mahalle or auto_mah

    new_row = pd.DataFrame([{
        "Saha ID": _clean_text(saha_id),
        "Latitude": _clean_text(lat),
        "Longitude": _clean_text(lon),
        "İl": _clean_text(il),
        "İlçe": _clean_text(ilce),
        "Mahalle": _clean_text(mahalle)
    }])

    if not current_df.empty:
        current_df = current_df[current_df["Saha ID"] != _clean_text(saha_id)]
    
    updated_df = pd.concat([current_df, new_row], ignore_index=True)
    save_sahalar(updated_df)


def delete_saha(saha_id: str):
    current_df = load_sahalar()
    if not current_df.empty:
        updated_df = current_df[current_df["Saha ID"] != _clean_text(saha_id)]
        save_sahalar(updated_df)
