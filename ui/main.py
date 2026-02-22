"""
ReportLens Streamlit Arayüzü.
Analiz, Öz Değerlendirme, Tutarsızlık Analizi, Rapor Yönetimi sayfaları.
"""
import os
import sys

# Proje kök dizinini Python yoluna ekle (Streamlit ui/ altından çalıştığı için gerekli)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import streamlit as st

# ── Sayfa yapılandırması (İLK Streamlit çağrısı olmalı) ──────────────
st.set_page_config(
    page_title="ReportLens - Üniversite Kalite Raporu Analiz Portalı",
    page_icon="🔍",
    layout="wide",
)

from core.brain import QualityBrain
from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)

# ── Başlatma ───────────────────────────────────────────────────────

@st.cache_resource
def get_brain():
    try:
        return QualityBrain()
    except Exception as e:
        logger.error(f"Sistem başlatılamadı: {e}")
        return None

brain = get_brain()

def get_available_birimler():
    """İşlenmiş raporlardan mevcut birimleri listeler."""
    birimler = set()
    for f in Config.PROCESSED_DATA_DIR.glob("*.md"):
        parts = f.stem.split("_")
        if parts:
            birimler.add(parts[0])
    return sorted(list(birimler))

# ── Yan Menü ve Başlık ─────────────────────────────────────────────

st.sidebar.title("🔍 ReportLens")
st.sidebar.info("Yerel LLM Üniversite Kalite Raporu Analiz Sistemi")

tabs = st.tabs([
    "🏠 Ana Sayfa",
    "🤖 Kalite Analiz Uzmanı",
    "📄 Rapor Analizi",
    "📊 Öz Değerlendirme Raporu",
    "🔍 Tutarsızlık Analizi",
    "📁 Rapor Yönetimi",
    "⚙️ Ayarlar",
])

# ══════════════════════════════════════════════════════════════════════
# SAYFA 0: Ana Sayfa
# ══════════════════════════════════════════════════════════════════════

with tabs[0]:
    st.title("🚀 ReportLens'e Hoş Geldiniz")
    st.markdown(
        """
    ReportLens, üniversite kalite raporlarını **yerel bir yapay zeka** ile analiz etmenizi sağlayan sürdürülebilir bir sistemdir.

    ### 🛡️ Temel Prensipler
    1. **Veri Gizliliği:** Verileriniz asla internete çıkmaz. Ollama ile tamamen yerel çalışır.
    2. **Çok Ajanlı Mimari:** Analiz, Rapor Yazım, Tutarsızlık Kontrol ve Sahte Veri Üretim ajanları birlikte çalışır.
    3. **Qdrant Vektör DB:** Hızlı semantik arama ve metadata filtreleme.
    """
    )

    if brain:
        status = brain.get_status()
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📄 Ham Rapor", status["ham_rapor_sayisi"])
        col2.metric("📝 İşlenmiş Rapor", status["islenmiş_rapor_sayisi"])
        col3.metric("🧠 Vektör Nokta", status["vektor_db"].get("toplam_nokta", 0))
        col4.metric("🤖 Model", status["model"])

        birimler = get_available_birimler()
        if birimler:
            st.markdown("### 📚 Mevcut Birimler")
            st.write(", ".join([f"**{b}**" for b in birimler]))
    else:
        st.error("Sistem başlatılamadı. Lütfen Ayarlar sayfasını kontrol edin.")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 1: Kalite Analiz Uzmanı
# ══════════════════════════════════════════════════════════════════════

with tabs[1]:
    st.header("🤖 Kalite Analiz Uzmanı")
    
    with st.expander("ℹ️ Nasıl Çalışır?", expanded=False):
        st.info("""
        **Çalışma Mantığı:**
        1. **RAG (Retrieval-Augmented Generation)** kullanır.
        2. Veritabanındaki tüm raporlardan sorunuzla en alakalı bölümleri bulur.
        3. Bu bölümleri bağlam (context) olarak LLM'e (llama3.1) iletir.
        4. LLM sadece bu verilere dayanarak size doğru ve kanıta dayalı bir yanıt üretir.
        
        **İpucu:** Daha spesifik sorular sorarak (örn: 'Fen Fakültesi 2024 hedefleri nelerdir?') daha iyi sonuçlar alabilirsiniz.
        """)
    st.write("Raporlar hakkında her şeyi sorabilirsiniz.")

    if not brain:
        st.error("Sistem başlatılamadı. Lütfen Ayarlar sayfasını kontrol edin.")
    else:
        # Sohbet Geçmişi
        if "messages" not in st.session_state:
            st.session_state.messages = []

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if prompt := st.chat_input("Hangi konuda analiz istersiniz?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Düşünüyor..."):
                    response = brain.analyze(prompt)
                    st.markdown(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Temizleme butonu
            if st.button("Sohbeti Temizle"):
                st.session_state.messages = []
                st.rerun()

# ══════════════════════════════════════════════════════════════════════
# SAYFA 2: Rapor Analizi
# ══════════════════════════════════════════════════════════════════════

with tabs[2]:
    st.header("📄 Rapor Analizi")
    st.markdown("Belirli bir raporu seçerek içeriğinin detaylı analizini alabilirsiniz.")

    proc_files = [f.name for f in Config.PROCESSED_DATA_DIR.glob("*.md")]
    if not proc_files:
        st.warning("Analiz edilecek işlenmiş rapor bulunamadı. Lütfen Rapor Yönetimi'nden dosyaları işleyin.")
    else:
        selected_report = st.selectbox("Analiz edilecek raporu seçin", proc_files, key="analysis_report")
        
        if st.button("Raporu Analiz Et", type="primary"):
            if brain:
                with st.spinner("Rapor analiz ediliyor..."):
                    try:
                        result = brain.analyze_single_report(selected_report)
                        st.markdown("### 📊 Analiz Sonucu")
                        st.markdown(result)
                        
                        st.download_button(
                            "Analizi İndir (.md)",
                            data=result,
                            file_name=f"Analiz_{selected_report}",
                            mime="text/markdown"
                        )
                    except Exception as e:
                        st.error(f"Analiz hatası: {e}")
            else:
                st.error("Sistem başlatılamadı.")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 3: Öz Değerlendirme Raporu
# ══════════════════════════════════════════════════════════════════════

with tabs[3]:
    st.header("📊 Öz Değerlendirme Raporu Oluşturucu")
    
    with st.expander("ℹ️ Nasıl Çalışır?", expanded=False):
        st.info("""
        **Çalışma Mantığı:**
        1. **İteratif Analiz:** 6 farklı kalite kriteri (Eğitim, ArGe, Yönetim vb.) için veritabanında ayrı aramalar yapar.
        2. Her kriter için 'Güçlü Yönler' ve 'Gelişim Alanları' tespiti yapar.
        3. Tüm bu analizleri YÖKAK standartlarına uygun akademik bir rapor formatında birleştirir.
        
        **Sonuç:** Yapılandırılmış, kapsamlı ve resmi formatta bir öz değerlendirme raporu elde edersiniz.
        """)
    st.markdown("Birden fazla kalite raporundan kapsamlı bir Öz Değerlendirme Raporu üretir.")

    if not brain:
        st.error("Sistem başlatılamadı.")
    else:
        birimler = get_available_birimler()
        if not birimler:
            st.warning("Analiz için birim verisi bulunamadı.")
        else:
            birim = st.selectbox("Birim Seçin", birimler)
            yil = st.text_input("Yıl Filtresi (Opsiyonel)", placeholder="Örn: 2024")

            if st.button("🚀 Raporu Oluştur", type="primary"):
                with st.spinner(f"{birim} için rapor oluşturuluyor (bu işlem birkaç dakika sürebilir)..."):
                    try:
                        report = brain.generate_self_evaluation(birim, yil if yil else None)
                        st.markdown("### 📄 Üretilen Rapor")
                        st.markdown(report)

                        st.download_button(
                            label="📥 Raporu İndir (.md)",
                            data=report,
                            file_name=f"Oz_Degerlendirme_{birim}_{yil}.md",
                            mime="text/markdown",
                        )
                    except Exception as e:
                        st.error(f"Rapor oluşturma hatası: {e}")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 4: Tutarsızlık Analizi
# ══════════════════════════════════════════════════════════════════════

with tabs[4]:
    st.header("🔍 Tutarsızlık Analizi")
    st.markdown("Rapor verileri ile harici metinleri veya anket yanıtlarını kıyaslayarak tutarlılık denetimi yapın.")

    if not brain:
        st.error("Sistem başlatılamadı.")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            proc_files = [f.name for f in Config.PROCESSED_DATA_DIR.glob("*.md")]
            selected_filename = st.selectbox("Kıyaslanacak Rapor (Opsiyonel)", ["Tümü"] + proc_files)
            target_file = None if selected_filename == "Tümü" else selected_filename
            
            st.subheader("Otomatik Üretim")
            mode = st.radio("Üretilecek Veri Tipi", ["Tutarsız", "Tutarlı", "Karmaşık"], horizontal=True)
            
            if st.button("Örnek Veri Üret (Ajan ile)"):
                if target_file:
                    with st.spinner("Örnek veri üretiliyor..."):
                        mock_data = brain.generate_mock_data(target_file, mode)
                        st.session_state["comparison_text"] = mock_data
                else:
                    st.warning("Lütfen veri üretmek için önce bir rapor seçin.")

        with col2:
            comparison_text = st.text_area(
                "Karşılaştırılacak Metin veya Anket Yanıtları",
                value=st.session_state.get("comparison_text", ""),
                height=250,
                placeholder="Buraya karşılaştırılacak metni yapıştırın veya otomatik üretin...",
            )

        if st.button("Analizi Başlat", type="primary"):
            if not comparison_text.strip():
                st.warning("Lütfen karşılaştırılacak bir metin girin.")
            else:
                with st.spinner("Derinlemesine tutarsızlık analizi yapılıyor (bu işlem raporun uzunluğuna göre vakit alabilir)..."):
                    try:
                        result = brain.check_consistency(comparison_text, filename=target_file)
                        
                        st.success("✅ Analiz Tamamlandı!")
                        
                        # Sonucu daha iyi yapılandırılmış göster
                        st.markdown(result)
                        
                        st.download_button(
                            label="📥 Detaylı Analiz Raporunu İndir (.md)",
                            data=result,
                            file_name=f"Tutarsizlik_Analizi_{selected_filename}.md",
                            mime="text/markdown",
                        )
                    except Exception as e:
                        st.error(f"Analiz hatası: {e}")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 5: Rapor Yönetimi
# ══════════════════════════════════════════════════════════════════════

with tabs[5]:
    st.header("📁 Rapor Yönetimi")
    st.markdown("### 📤 Yeni Rapor Yükle")
    uploaded_files = st.file_uploader(
        "PDF, DOCX, Excel veya CSV dosyaları seçin",
        type=["pdf", "docx", "xlsx", "xls", "csv"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        for uploaded_file in uploaded_files:
            save_path = Config.RAW_DATA_DIR / uploaded_file.name
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success(f"✅ {uploaded_file.name} yüklendi.")

        if st.button("⚙️ Yüklenen Dosyaları İşle ve İndeksle", type="primary"):
            if brain:
                with st.spinner("Dosyalar işleniyor ve indeksleniyor..."):
                    result = brain.process_and_index()
                    st.success(
                        f"✅ {result['islenen_dosya']} dosya işlendi, "
                        f"{result['indekslenen_chunk']} chunk indekslendi."
                    )
                    st.cache_resource.clear()
                    st.rerun()

    st.markdown("---")
    st.markdown("### 📋 Mevcut Raporlar")
    if Config.RAW_DATA_DIR.exists():
        files_data = []
        for f in sorted(Config.RAW_DATA_DIR.glob("**/*")):
            if f.suffix.lower() in [".pdf", ".docx", ".xlsx", ".xls", ".csv"]:
                parts = f.stem.split("_")
                birim = parts[0] if parts else "-"
                yil = parts[1] if len(parts) >= 2 and parts[1].isdigit() else "-"
                tur = " ".join(parts[2:]) if len(parts) >= 3 else "-"
                size_mb = f.stat().st_size / (1024 * 1024)
                processed = (Config.PROCESSED_DATA_DIR / f"{f.stem}.md").exists()

                files_data.append({
                    "Birim": birim, "Yıl": yil, "Tür": tur, "Dosya": f.name,
                    "Boyut (MB)": f"{size_mb:.1f}", "İşlenmiş": "✅" if processed else "❌"
                })

        if files_data:
            import pandas as pd
            df = pd.DataFrame(files_data)
            st.dataframe(df, width="stretch", hide_index=True)
            st.caption(f"Toplam: {len(files_data)} rapor")
        else:
            st.info("Henüz rapor yüklenmemiş.")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 6: Ayarlar
# ══════════════════════════════════════════════════════════════════════

with tabs[6]:
    st.header("⚙️ Ayarlar")
    if brain:
        status = brain.get_status()
        st.markdown("### 🔧 Yapılandırma")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Ollama URL:** `{status['ollama_url']}`")
            st.write(f"**Model:** `{status['model']}`")
        with col2:
            st.write(f"**Chunk Boyutu:** `{Config.CHUNK_SIZE}`")
            st.write(f"**Arama Sonuç (k):** `{Config.SEARCH_K}`")

        st.markdown("### 📊 Vektör Veritabanı")
        st.json(status["vektor_db"])

        st.markdown("### 🔄 Bakım")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Raporları Yeniden İşle"):
                with st.spinner("İşleniyor..."):
                    result = brain.process_and_index()
                    st.success(f"✅ {result['islenen_dosya']} dosya işlendi.")
        with col2:
            if st.button("🗑️ Veritabanını Sıfırla"):
                with st.spinner("Sıfırlanıyor..."):
                    result = brain.process_and_index(force_reindex=True)
                    st.success("✅ Veritabanı sıfırlandı ve yeniden indekslendi.")
                    st.cache_resource.clear()
                    st.rerun()
    else:
        st.error("🔴 Sistem başlatılamadı. Ollama çalışıyor mu?")
