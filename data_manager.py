"""
data_manager.py
----------------
YEDAŞ Planlı Kesinti Takip Uygulaması - Esnek Veri Yönetimi Modülü
"""

import os
import io
import re
import pandas as pd

SAHA_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahalar.csv")
COLUMNS = ["Saha ID", "İl", "İlçe", "Mahalle"]


def _clean_text_simple(x: str) -> str:
    if pd.isna(x) or x is None:
        return ""
    x = str(x).strip().lower()
    replacements = {"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
    for src, tgt in replacements.items():
        x = x.replace(src, tgt)
    return x.replace(" ", "")


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    # 1. KML veya Açıklama sütunundan SITE_NO çek
    if "Açıklama" in df.columns or "Description" in df.columns:
        desc_col = "Açıklama" if "Açıklama" in df.columns else "Description"
        site_ids = df[desc_col].astype(str).str.extract(r'SITE_NO=\s*(\d+)')
        if 0 in site_ids.columns and not site_ids[0].isnull().all():
            df["Saha ID"] = site_ids[0]

    # 2. Sütun Adlarını Eşleştir
    rename_map = {}
    for col in df.columns:
        clean_col = _clean_text_simple(col)
        
        if "saha" in clean_col or clean_col in ["id", "sahaid", "sahano", "kodu", "site_no"]:
            rename_map[col] = "Saha ID"
        elif clean_col in ["il", "sehir", "province", "city"]:
            rename_map[col] = "İl"
        elif clean_col in ["ilce", "district", "town"]:
            rename_map[col] = "İlçe"
        elif clean_col in ["mahalle", "mah", "neighborhood", "semt"]:
            rename_map[col] = "Mahalle"

    df = df.rename(columns=rename_map)

    # 3. Saha ID yoksa Placemark/Name sütununu Saha ID yap
    if "Saha ID" not in df.columns or df["Saha ID"].isnull().all():
        for candidate in ["Placemark Ad", "Name", "Saha Adı"]:
            if candidate in df.columns:
                df["Saha ID"] = df[candidate]
                break

    # 4. KML Folder yapısından İl / İlçe çıkarma (Eğer ayrı il/ilçe sütunları yoksa)
    if "Folder" in df.columns and ("İl" not in df.columns or df["İl"].isnull().all()):
        # Folder sütunundaki "SAMSUN / ATAKUM" veya "ORDU/ALTINORDU" yapılarını böl
        folder_split = df["Folder"].astype(str).str.split(r'[/\\-]', expand=True)
        if folder_split.shape[1] >= 1:
            df["İl"] = folder_split[0].str.strip()
        if folder_split.shape[1] >= 2:
            df["İlçe"] = folder_split[1].str.strip()

    # Eksik sütunları oluştur
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS].copy()

    # Metin temizleme
    for col in COLUMNS:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace(["nan", "None", "null", "NaN"], "")

    # Geçersiz satırları süz
    df = df[df["Saha ID"] != ""]
    df = df[~df["Saha ID"].str.startswith(";")]

    return df.reset_index(drop=True)


def read_flexible_file(file_or_path) -> pd.DataFrame:
    try:
        if isinstance(file_or_path, str):
            if file_or_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_or_path, dtype=str)
                return _normalize_df(df)
            else:
                encodings_to_try = ["utf-8-sig", "latin5", "iso-8859-9", "utf-8"]
                for enc in encodings_to_try:
                    try:
                        df = pd.read_csv(file_or_path, dtype=str, encoding=enc, sep=None, engine='python')
                        return _normalize_df(df)
                    except Exception:
                        continue
        else:
            file_name = getattr(file_or_path, "name", "").lower()
            if file_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_or_path, dtype=str)
                return _normalize_df(df)
            else:
                bytes_data = file_or_path.getvalue()
                encodings_to_try = ["utf-8-sig", "latin5", "iso-8859-9", "utf-8"]
                for enc in encodings_to_try:
                    try:
                        content = bytes_data.decode(enc)
                        sep = ";" if ";" in content.split("\n")[0] else ","
                        df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)
                        return _normalize_df(df)
                    except Exception:
                        continue
    except Exception as e:
        print(f"Okuma hatası: {e}")
        
    return pd.DataFrame(columns=COLUMNS)


def load_sahalar() -> pd.DataFrame:
    if not os.path.exists(SAHA_CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)
    return read_flexible_file(SAHA_CSV_PATH)


def save_sahalar(df: pd.DataFrame) -> None:
    df = _normalize_df(df)
    df = df.drop_duplicates(subset=["Saha ID"], keep="last")
    df.to_csv(SAHA_CSV_PATH, index=False, encoding="utf-8-sig")


def add_or_update_saha(saha_id: str, il: str = "", ilce: str = "", mahalle: str = "") -> pd.DataFrame:
    df = load_sahalar()
    saha_id = str(saha_id).strip()

    if not df.empty and "Saha ID" in df.columns and saha_id in df["Saha ID"].values:
        idx = df.index[df["Saha ID"] == saha_id][0]
        df.loc[idx, ["İl", "İlçe", "Mahalle"]] = [il.strip(), ilce.strip(), mahalle.strip()]
    else:
        new_row = pd.DataFrame([{
            "Saha ID": saha_id, "İl": il.strip(), "İlçe": ilce.strip(), "Mahalle": mahalle.strip()
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    save_sahalar(df)
    return df


def delete_saha(saha_id: str) -> pd.DataFrame:
    df = load_sahalar()
    if not df.empty and "Saha ID" in df.columns:
        df = df[df["Saha ID"] != str(saha_id).strip()]
        save_sahalar(df)
    return df


def bulk_upload(new_df, mode: str = "append_update") -> pd.DataFrame:
    if not isinstance(new_df, pd.DataFrame):
        new_df = read_flexible_file(new_df)
    else:
        new_df = _normalize_df(new_df)

    if mode == "replace":
        final_df = new_df.drop_duplicates(subset=["Saha ID"], keep="last")
    else:
        current_df = load_sahalar()
        combined = pd.concat([current_df, new_df], ignore_index=True)
        final_df = combined.drop_duplicates(subset=["Saha ID"], keep="last")

    save_sahalar(final_df)
    return final_df
