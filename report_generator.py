"""
report_generator.py
---------------------
Kesinti tablosunu PDF ve JPG (görsel) formatında dışa aktarma fonksiyonları.

- PDF: reportlab ile temiz, sayfa genişliğine oturan bir tablo raporu üretir.
- JPG: matplotlib ile DataFrame'i bir tablo görseline dönüştürür (harici
  bir tarayıcı/wkhtmltoimage bağımlılığı gerektirmez, bu yüzden Streamlit
  Cloud gibi ortamlarda da sorunsuz çalışır).
"""

import io
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def generate_pdf(df: pd.DataFrame, title: str = "YEDAŞ Planlı Kesinti Raporu") -> bytes:
    """Verilen DataFrame'i temiz bir PDF tablo raporuna dönüştürür ve bytes olarak döner."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(title, styles["Title"]))
    elements.append(Paragraph(f"Oluşturulma Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles["Normal"]))
    elements.append(Spacer(1, 0.5 * cm))

    if df.empty:
        elements.append(Paragraph("Seçilen filtre için eşleşen kesinti bulunamadı.", styles["Normal"]))
    else:
        # Başlık satırı + veri satırları
        data = [list(df.columns)] + df.astype(str).values.tolist()
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3864")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f7")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ]))
        elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def generate_jpg(df: pd.DataFrame, title: str = "YEDAŞ Planlı Kesinti Raporu") -> bytes:
    """Verilen DataFrame'i JPG görsel formatında bir tablo olarak render eder ve bytes olarak döner."""
    n_rows = max(len(df), 1)
    n_cols = max(len(df.columns), 1)

    fig_height = 1 + 0.35 * n_rows
    fig_width = max(10, 1.8 * n_cols)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    ax.set_title(f"{title}\n{datetime.now().strftime('%d.%m.%Y %H:%M')}", fontsize=12, fontweight="bold", pad=20)

    if df.empty:
        ax.text(0.5, 0.5, "Seçilen filtre için eşleşen kesinti bulunamadı.", ha="center", va="center", fontsize=11)
    else:
        tbl = ax.table(
            cellText=df.astype(str).values,
            colLabels=df.columns,
            cellLoc="left",
            loc="center",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8)
        tbl.scale(1, 1.5)
        tbl.auto_set_column_width(col=list(range(n_cols)))

        # Başlık satırını renklendir
        for col_idx in range(n_cols):
            header_cell = tbl[0, col_idx]
            header_cell.set_facecolor("#1f3864")
            header_cell.set_text_props(color="white", fontweight="bold")

    buffer = io.BytesIO()
    fig.savefig(buffer, format="jpg", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()
