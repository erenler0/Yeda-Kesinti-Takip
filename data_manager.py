"""
data_manager.py
----------------
YEDAŞ Planlı Kesinti Takip Uygulaması - Hızlı Saha Yönetimi
"""

import os
import io
import pandas as pd

SAHA_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahalar.csv")
COLUMNS = ["Saha ID", "Latitude", "Longitude", "İl", "İlçe", "Mahalle"]


def _clean_text(x) -> str:
    if pd.isna(x) or x is None:
        return ""
    return str(x).strip()


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    # 1. KML veya Açıklama metninden SITE_NO ayıklama
    if "Açıklama" in df.columns or "Description" in df.columns:
        desc_col = "Açıklama" if "Açıklama" in df.columns else "Description"
        site_ids = df[desc_col].astype(str).str.extract(r'SITE_NO=\s*(\d+)')
        if 0 in site_ids.columns and not site_ids[0].isnull().all():
            df["Saha ID"] = site_ids[0]

    # 2. Sütun Adlarını Eşleştirme (Esnek İsimler)
    rename_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower()
        
        # Saha ID
        if c_clean in ["saha id", "site_no", "site no", "saha_id", "id", "kodu", "placemark ad", "name"]:
            rename_map[col] = "Saha ID"
        # Latitude
        elif c_clean in ["latitude", "lat", "enlem", "y", "y_coord", "lat_coord"]:
            rename_map[col] = "Latitude"
        # Longitude
        elif c_clean in ["longitude", "long", "lng", "boylam", "x", "x_coord", "long_coord"]:
            rename_map[col] = "Longitude"
        # İl / İlçe / Mahalle
        elif c_clean in ["il", "sehir", "şehir", "province", "city"]:
            rename_map[col] = "İl"
        elif c_clean in ["ilce", "ilçe", "district", "town"]:
            rename_map[col] = "İlçe"
        elif c_clean in ["mahalle", "mah", "neighbourhood"]:
            rename_map[col] = "Mahalle"

    df = df.rename(columns=rename_map)

    # Saha ID yoksa ilk sütunu Saha ID yap
    if "Saha ID" not in df.columns or df["Saha ID"].isnull().all():
        df["Saha ID"] = df.iloc[:, 0]

    # Eksik sütunları oluştur
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
    """Excel veya CSV dosyasını okur, hızlıca kaydedip döndürür."""
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

    if mode == "replace":
        final_df = normalized_df
    else:
        current_df = load_sahalar()
        final_df = pd.concat([current_df, normalized_df], ignore_index=True)

    save_sahalar(final_df)
    return final_df


def add_or_update_saha(saha_id: str, il: str, ilce: str, mahalle: str, lat: str = "", lon: str = ""):
    current_df = load_sahalar()
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
