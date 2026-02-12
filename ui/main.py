import streamlit as st
import os
import pandas as pd
from core.brain import QualityBrain
import logging

# Log ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Beyin kurulumu
@st.cache_resource
def get_brain():
    PROCESSED_DATA = "Data/processed"
    VECTOR_DB = "Data/vector_db"
    brain = QualityBrain(PROCESSED_DATA, VECTOR_DB)
    # Vektör DB yoksa veya boşsa indeksle (Opsiyonel: Bunu bir butona da bağlayabilirsin)
    if not os.path.exists(VECTOR_DB) or not os.listdir(VECTOR_DB):
        with st.spinner("Raporlar indeksleniyor..."):
            brain.index_documents()
    brain.create_agents()
    return brain

brain = get_brain()

# Sayfa Yapılandırması
st.set_page_config(
    page_title="ReportLens - Üniversite Kalite Raporu Analiz Portalı",
    page_icon="🔍",
    layout="wide"
)

# Kenar Çubuğu (Sidebar)
st.sidebar.title("🔍 ReportLens")
st.sidebar.info("Llama 3.1 8B Yerel Analiz Sistemi")

menu = st.sidebar.selectbox("Gezinti", ["Ana Sayfa", "Analiz Uzmanı", "Rapor Yükle", "Ayarlar"])

# Ana Sayfa
if menu == "Ana Sayfa":
    st.title("🚀 ReportLens'e Hoş Geldiniz")
    st.markdown("""
    ReportLens, üniversite kalite raporlarını **yerel bir yapay zeka** ile analiz etmenizi sağlayan sürdürülebilir bir sistemdir.
    
    ### 🛡️ Temel Prensiplerimiz
    1. **Veri Gizliliği:** Verileriniz asla internete çıkmaz. Ollama ile tamamen yerel çalışır.
    2. **Sürdürülebilirlik:** Açık kaynaklı modeller ve temiz kod mimarisi.
    3. **Hız:** RTX 4070 GPU desteği ile saniyeler içinde analiz.
    """)
    
    # İstatistikler
    col1, col2, col3 = st.columns(3)
    raw_files = len(os.listdir("Data/raw_data")) if os.path.exists("Data/raw_data") else 0
    proc_files = len(os.listdir("Data/processed")) if os.path.exists("Data/processed") else 0
    col1.metric("Toplam Ham Rapor", raw_files)
    col2.metric("İşlenmiş Rapor", proc_files)
    col3.metric("Analiz Uzmanı", "Aktif")

# Analiz Uzmanı
elif menu == "Analiz Uzmanı":
    st.title("🤖 Kalite Analiz Uzmanı")
    st.write("Raporlar hakkında her şeyi sorabilirsiniz.")
    
    query = st.text_input("Sorgunuzu buraya yazın:", placeholder="Örn: Fen fakültesinin son 5 yıldaki gelişimini özetle.")
    
    if st.button("Analiz Et"):
        if query:
            with st.spinner("Ajanlar raporları tarıyor ve analiz hazırlıyor..."):
                try:
                    response = brain.analyze(query)
                    st.markdown("### 📋 Analiz Sonucu")
                    st.write(response.content)
                except Exception as e:
                    st.error(f"Analiz sırasında bir hata oluştu: {str(e)}")
        else:
            st.warning("Lütfen bir soru girin.")

# Rapor Yükle Sayfası
elif menu == "Rapor Yükle":
    st.title("📁 Yeni Rapor Ekle")
    uploaded_file = st.file_uploader("PDF veya DOCX dosyası seçin", type=["pdf", "docx"])
    if uploaded_file:
        with open(os.path.join("Data/raw_data", uploaded_file.name), "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"{uploaded_file.name} başarıyla eklendi. İşlemek için terminalden processor'u çalıştırın veya sistemi yeniden başlatın.")

# Ayarlar
elif menu == "Ayarlar":
    st.title("⚙️ Sistem Ayarları")
    st.write(f"Ollama URL: `{brain.ollama_url}`")
    st.write("Model: **Llama-3.1-8B**")
    st.button("Vektör Veritabanını Yenile (Re-index)", on_click=lambda: brain.index_documents())
