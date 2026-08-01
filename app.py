"""
app.py
-------
YEDAŞ Planlı Kesinti Takip ve Saha Yönetim Uygulaması - Ana Streamlit Uygulaması

Çalıştırmak için:
    streamlit run app.py

Sayfalar:
    1) Dashboard         -> Özet KPI kartları + Plotly Grafikleri + Zaman filtreli kesinti tablosu + PDF/JPG export
    2) Veri Yönetimi     -> Toplu CSV yükleme + tekil saha ekleme/güncelleme
"""

import pandas as pd
import streamlit as st
import plotly.express as px

import data_manager as dm
import yedas_scraper as ys
import report_generator as rg

# ------------------------------------------------------------------
# Sayfa Ayarları & Özel Tema / CSS
# ------------------------------------------------------------------
st.set_page_config(
    page_title="YEDAŞ Planlı Kesinti Takip Sistemi",
    page_icon="⚡",
    layout="wide",
)

def apply_custom_theme():
    st.markdown("""
        <style>
        /* Ana Görünüm ve Arka Plan Dokunuşları */
        .main {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        
        /* KPI Metrik Kartları */
        .metric-card {
            background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
            border: 1px solid #334155;
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
            text-align: center;
            margin-bottom: 15px;
        }
        .metric-value {
            font-size: 1.8rem;
            font-weight: 800;
            color: #38BDF8;
            margin-top: 4px;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #94A3B8;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }

        /* Başlık Stili */
        .header-title {
            background: linear-gradient(90deg, #38BDF8 0%, #818CF8 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2rem;
            font-weight: 800;
        }

        /* Streamlit Tablo Kenarlık Çerçevesi */
        .stDataFrame {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid #334155;
        }
        </style>
    """, unsafe_allow_html=True)

apply_custom_theme()

# ------------------------------------------------------------------
# Kenar Çubuğu (Sidebar) - Sayfa Navigasyonu & Kalıcı Veri Yükleme
# ------------------------------------------------------------------
st.sidebar.title("⚡ YEDAŞ Kesinti Takip")
page = st.sidebar.radio("Sayfa Seçin", ["📊 Dashboard", "🗂️ Veri Yönetimi"])

# Veritabanından/Diskten kalıcı sahaları çek
sahalar_df = dm.load_sahalar()

st.sidebar.markdown("---")
st.sidebar.metric("Kayıtlı Saha Sayısı", len(sahalar_df))


# ====================================================================
# SAYFA 1: DASHBOARD
# ====================================================================
if page == "📊 Dashboard":
    st.markdown('<h1 class="header-title">📊 Planlı Kesinti Dashboard</h1>', unsafe_allow_html=True)
    st.caption("Kayıtlı sahalarınız ile YEDAŞ'ın güncel planlı kesinti duyurularının eşleştirilmiş görünümü.")
    st.write("")

    if sahalar_df.empty:
        st.warning("⚠️ Henüz sisteme kayıtlı saha bulunmuyor. Lütfen önce **Veri Yönetimi** sayfasından saha ekleyin.")
    else:
        # ---- Hızlı Zaman Filtreleri ----
        st.subheader("⏱️ Zaman Filtresi")
        col1, col2, col3, col_spacer = st.columns([1, 1, 1, 3])

        if "secili_filtre" not in st.session_state:
            st.session_state.secili_filtre = "Bugün"

        with col1:
            if st.button("📅 Bugün", use_container_width=True, type="primary" if st.session_state.secili_filtre == "Bugün" else "secondary"):
                st.session_state.secili_filtre = "Bugün"
                st.rerun()
        with col2:
            if st.button("📅 3 Günlük", use_container_width=True, type="primary" if st.session_state.secili_filtre == "3 Günlük" else "secondary"):
                st.session_state.secili_filtre = "3 Günlük"
                st.rerun()
        with col3:
            if st.button("📅 7 Günlük", use_container_width=True, type="primary" if st.session_state.secili_filtre == "7 Günlük" else "secondary"):
                st.session_state.secili_filtre = "7 Günlük"
                st.rerun()

        st.info(f"Aktif zaman aralığı: **{st.session_state.secili_filtre}**")

        # ---- Veri Çekme ve Eşleştirme ----
        with st.spinner("YEDAŞ canlı verileri kontrol ediliyor..."):
            kesintiler_df, is_demo = ys.get_kesintiler(sahalar_df)
            matched_df = ys.match_sahalar_with_kesintiler(sahalar_df, kesintiler_df)
            filtered_df = ys.filter_by_period(matched_df, st.session_state.secili_filtre)

        if is_demo:
            st.warning(
                "⚠️ YEDAŞ canlı verisine şu an ulaşılamadı (site yapısı JS-tabanlı olabilir veya ağ erişimi "
                "kısıtlı). Aşağıda **DEMO/örnek veri** gösterilmektedir. Gerçek entegrasyon için "
                "`yedas_scraper.py` içindeki `_fetch_live_data` fonksiyonunu sitenin gerçek API/HTML "
                "yapısına göre güncelleyin."
            )

        # ---- ÖZET METRİK KARTLARI (KPI Box) ----
        st.markdown("### 📈 Özet Göstergeler")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        toplam_kesinti = len(filtered_df)
        etkilenen_il_sayisi = filtered_df["İl"].nunique() if not filtered_df.empty and "İl" in filtered_df.columns else 0
        en_cok_il = filtered_df["İl"].mode()[0] if not filtered_df.empty and "İl" in filtered_df.columns and not filtered_df["İl"].empty else "-"
        
        with kpi1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Etkilenen Saha Sayısı</div>
                    <div class="metric-value">{toplam_kesinti}</div>
                </div>
            """, unsafe_allow_html=True)
            
        with kpi2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Etkilenen İl Sayısı</div>
                    <div class="metric-value" style="color:#FBBF24;">{etkilenen_il_sayisi}</div>
                </div>
            """, unsafe_allow_html=True)

        with kpi3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">En Çok Kesinti Olan İl</div>
                    <div class="metric-value" style="color:#F43F5E;">{en_cok_il}</div>
                </div>
            """, unsafe_allow_html=True)

        with kpi4:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">Sistem Durumu</div>
                    <div class="metric-value" style="color:#10B981;">{"CANLI" if not is_demo else "DEMO"}</div>
                </div>
            """, unsafe_allow_html=True)

        # ---- GRAFİKLER (PLOTLY) ----
        if not filtered_df.empty and "İl" in filtered_df.columns:
            st.markdown("### 📊 Kesinti Dağılım Grafikleri")
            g_col1, g_col2 = st.columns(2)

            with g_col1:
                # İllere Göre Kesinti Dağılımı
                il_counts = filtered_df["İl"].value_counts().reset_index()
                il_counts.columns = ["İl", "Saha Sayısı"]
                fig_il = px.bar(
                    il_counts, 
                    x="İl", 
                    y="Saha Sayısı", 
                    title="İllere Göre Etkilenen Saha Dağılımı",
                    color="Saha Sayısı", 
                    color_continuous_scale="Viridis"
                )
                fig_il.update_layout(template="plotly_dark", height=320, margin=dict(l=20, r=20, t=40, b=20))
                st.plotly_chart(fig_il, use_container_width=True)

            with g_col2:
                # Kesinti Nedenleri Dağılımı (Varsa)
                reason_col = "Açıklama/Nedeni" if "Açıklama/Nedeni" in filtered_df.columns else "Neden"
                if reason_col in filtered_df.columns:
                    reason_counts = filtered_df[reason_col].value_counts().reset_index()
                    reason_counts.columns = ["Neden", "Adet"]
                    fig_reason = px.pie(
                        reason_counts, 
                        values="Adet", 
                        names="Neden", 
                        title="Kesinti Nedenleri Dağılımı",
                        hole=0.4
                    )
                    fig_reason.update_layout(template="plotly_dark", height=320, margin=dict(l=20, r=20, t=40, b=20))
                    st.plotly_chart(fig_reason, use_container_width=True)

        # ---- Kesinti Tablosu ----
        st.markdown("### 📋 Eşleşen Kesinti Tablosu")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)
        st.caption(f"Toplam **{len(filtered_df)}** kesinti kaydı eşleşti.")

        # ---- Dışa Aktarma Butonları ----
        st.markdown("---")
        st.subheader("📥 Raporu Dışa Aktar")
        exp_col1, exp_col2 = st.columns(2)

        with exp_col1:
            pdf_bytes = rg.generate_pdf(filtered_df, title=f"YEDAŞ Planlı Kesinti Raporu ({st.session_state.secili_filtre})")
            st.download_button(
                label="📄 PDF Olarak İndir",
                data=pdf_bytes,
                file_name=f"yedas_kesinti_raporu_{st.session_state.secili_filtre}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        with exp_col2:
            jpg_bytes = rg.generate_jpg(filtered_df, title=f"YEDAŞ Planlı Kesinti Raporu ({st.session_state.secili_filtre})")
            st.download_button(
                label="🖼️ JPG Olarak İndir",
                data=jpg_bytes,
                file_name=f"yedas_kesinti_raporu_{st.session_state.secili_filtre}.jpg",
                mime="image/jpeg",
                use_container_width=True,
            )


# ====================================================================
# SAYFA 2: VERİ YÖNETİMİ
# ====================================================================
elif page == "🗂️ Veri Yönetimi":
    st.markdown('<h1 class="header-title">🗂️ Saha Veri Yönetimi</h1>', unsafe_allow_html=True)
    st.caption("Veritabanındaki saha listenizi buradan yönetebilir, toplu yükleme yapabilir veya tekil kayıtlar ekleyebilirsiniz.")
    st.write("")

    tab1, tab2, tab3 = st.tabs(["📤 Toplu Yükleme (CSV)", "✏️ Tekil Ekle / Güncelle", "📋 Kayıtlı Sahalar"])

    # ---------------- TAB 1: TOPLU YÜKLEME ----------------
    with tab1:
        st.subheader("Toplu CSV Yükleme")
        st.markdown(
            "CSV dosyanızda şu sütunlar bulunmalıdır (sütun sırası önemli değildir): "
            "`Saha ID`, `İl`, `İlçe`, `Mahalle`"
        )

        upload_mode = st.radio(
            "Yükleme Modu",
            ["Mevcut veriye ekle / güncelle (önerilen)", "Mevcut veri tabanını sıfırla ve yenisiyle değiştir"],
            index=0,
        )

        uploaded_file = st.file_uploader("CSV dosyası seçin", type=["csv"])

        if uploaded_file is not None:
            try:
                new_df = pd.read_csv(uploaded_file, dtype=str, encoding="utf-8-sig")
            except Exception:
                uploaded_file.seek(0)
                new_df = pd.read_csv(uploaded_file, dtype=str, encoding="latin5")

            st.write("Yüklenen dosyadan önizleme:")
            st.dataframe(new_df.head(10), use_container_width=True, hide_index=True)
            st.caption(f"Dosyada toplam {len(new_df)} satır bulundu.")

            mode = "replace" if upload_mode.startswith("Mevcut veri tabanını sıfırla") else "append_update"

            if mode == "replace":
                st.error("⚠️ Bu işlem mevcut TÜM saha veri tabanını silip yenisiyle değiştirecektir!")

            if st.button("✅ Yüklemeyi Onayla ve Kalıcı Kaydet", type="primary"):
                result_df = dm.bulk_upload(new_df, mode=mode)
                st.success(f"İşlem tamamlandı. Veriler diske kalıcı olarak kaydedildi. Sistemde şu an toplam {len(result_df)} saha kayıtlı.")
                st.rerun()

    # ---------------- TAB 2: TEKİL EKLE / GÜNCELLE ----------------
    with tab2:
        st.subheader("Tekil Saha Ekle / Güncelle")
        st.caption("Girilen Saha ID sistemde zaten varsa, bilgileri güncellenir. Yoksa yeni kayıt olarak eklenir.")

        with st.form("tekil_saha_form", clear_on_submit=True):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                saha_id = st.text_input("Saha ID *")
                il = st.text_input("İl *")
            with f_col2:
                ilce = st.text_input("İlçe *")
                mahalle = st.text_input("Mahalle *")

            submitted = st.form_submit_button("💾 Kaydet / Güncelle", type="primary")

            if submitted:
                if not saha_id.strip() or not il.strip() or not ilce.strip() or not mahalle.strip():
                    st.error("Lütfen tüm alanları doldurun.")
                else:
                    dm.add_or_update_saha(saha_id, il, ilce, mahalle)
                    st.success(f"'{saha_id}' kodlu saha başarıyla kaydedildi/güncellendi.")
                    st.rerun()

    # ---------------- TAB 3: KAYITLI SAHALAR ----------------
    with tab3:
        st.subheader("Sistemde Kayıtlı Tüm Sahalar")
        current_df = dm.load_sahalar()

        search_term = st.text_input("🔍 Ara (Saha ID, İl, İlçe veya Mahalle)")
        display_df = current_df
        if search_term.strip() and not current_df.empty:
            mask = current_df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)
            display_df = current_df[mask]

        st.dataframe(display_df, use_container_width=True, hide_index=True)
        st.caption(f"Gösterilen: {len(display_df)} / Toplam: {len(current_df)} saha")

        # Silme işlemi
        if not current_df.empty:
            st.markdown("---")
            st.markdown("**Kayıt Sil**")
            del_col1, del_col2 = st.columns([3, 1])
            with del_col1:
                saha_to_delete = st.selectbox("Silinecek Saha ID", options=current_df["Saha ID"].tolist())
            with del_col2:
                st.write("")
                st.write("")
                if st.button("🗑️ Sil", use_container_width=True):
                    dm.delete_saha(saha_to_delete)
                    st.success(f"'{saha_to_delete}' silindi.")
                    st.rerun()

        # Mevcut veriyi CSV olarak dışa aktarma imkanı (yedekleme amaçlı)
        st.download_button(
            "⬇️ Tüm Saha Verisini CSV Olarak İndir (Yedek)",
            data=current_df.to_csv(index=False, encoding="utf-8-sig"),
            file_name="sahalar_yedek.csv",
            mime="text/csv",
        )
