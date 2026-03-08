"""
ReportLens Streamlit Arayüzü.
Analiz, Öz Değerlendirme, Tutarsızlık Analizi, Rapor Yönetimi ve Test Sonuçları sayfaları.
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
    "⚖️ Rubrik Notlandırma",
    "🔍 Tutarsızlık Analizi",
    "📁 Rapor Yönetimi",
    "📊 Test Sonuçları",
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
        
        **İpucu:** Daha spesifik sorular sorarak (örn: 'Fen Fakültesi 2024 Öz Değerlendirme Raporu'nda belirtilen 'öğrenci merkezli öğrenme' hedefine ulaşmak için hangi somut eğitim teknolojileri veya yöntemleri devreye alınmıştır ve bu süreçte karşılaşılan riskler nasıl yönetilmektedir?') daha iyi sonuçlar alabilirsiniz.
        """)
    st.write("Raporlar hakkında her şeyi sorabilirsiniz.")

    if not brain:
        st.error("Sistem başlatılamadı. Lütfen Ayarlar sayfasını kontrol edin.")
    else:
        # ── Opsiyonel Filtreler ────────────────────────────────
        with st.expander("🔍 Filtreler (Opsiyonel — Daha doğru sonuçlar için kullanın)", expanded=False):
            st.info(
                "⚠️ **Önemli:** Belirli bir fakülte/birim hakkında soruyorsanız aşağıdan filtre seçin. "
                "Seçilmezse tüm birimlerin verileri karışabilir."
            )
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                available_birimler = ["🌐 Tüm Birimler (Filtresiz)"] + get_available_birimler()
                selected_birim_rag = st.selectbox(
                    "Birim Filtresi",
                    available_birimler,
                    help="Seçilen birime ait raporlardan arama yapılır.",
                    key="rag_birim",
                )
            with fcol2:
                yil_filter_rag = st.text_input(
                    "Yıl Filtresi",
                    placeholder="Örn: 2024 (boş bırakırsanız tüm yıllar)",
                    key="rag_yil",
                )
            birim_rag = None if selected_birim_rag.startswith("🌐") else selected_birim_rag
            yil_rag = yil_filter_rag.strip() if yil_filter_rag.strip() else None

        # ── Sohbet Geçmişi ──────────────────────────────────────────────────
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
                with st.spinner("Analiz ediliyor... (bu işlem 1-2 dk sürebilir)"):
                    result = brain.analyze(prompt, birim=birim_rag, yil=yil_rag)
                    # analyze() artık tuple dönüyor: (text, auto_birim, auto_yil)
                    if isinstance(result, tuple):
                        response, auto_birim, auto_yil = result
                        # Otomatik algılanan birim/yıl bilgisini göster
                        if auto_birim or auto_yil:
                            info_parts = []
                            if auto_birim:
                                info_parts.append(f"Birim: **{auto_birim}**")
                            if auto_yil:
                                info_parts.append(f"Yıl: **{auto_yil}**")
                            st.info(f"🔍 Otomatik algılanan filtre: {', '.join(info_parts)}")
                    else:
                        response = result
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
# SAYFA 4: Rubrik Notlandırma
# ══════════════════════════════════════════════════════════════════════

with tabs[4]:
    st.header("⚖️ Rubrik Notlandırma Sistemi")
    st.markdown("""
    Bu modül, seçilen raporları **YÖKAK Rubrik Standartlarına** göre 1-5 arası puanlar. 
    Ajan, her puan için rapordan somut kanıt sunmak zorundadır.
    """)

    if not brain:
        st.error("Sistem başlatılamadı.")
    else:
        proc_files = [f.name for f in Config.PROCESSED_DATA_DIR.glob("*.md")]
        if not proc_files:
            st.warning("Değerlendirilecek rapor bulunamadı.")
        else:
            selected_reports = st.multiselect(
                "Değerlendirilecek Raporları Seçin", 
                proc_files,
                help="Birden fazla rapor seçerek kıyaslama yapabilirsiniz."
            )

            if st.button("⚖️ Rubrik Analizini Başlat", type="primary"):
                if not selected_reports:
                    st.warning("Lütfen en az bir rapor seçin.")
                else:
                    with st.spinner("Rubrik değerlendirmesi yapılıyor (Her kriter için derinlemesine analiz edilir)..."):
                        try:
                            rubric_result = brain.evaluate_rubric(selected_reports)
                            st.success("✅ Rubrik Değerlendirmesi Tamamlandı!")
                            st.markdown(rubric_result)

                            st.download_button(
                                label="📥 Rubrik Raporunu İndir (.md)",
                                data=rubric_result,
                                file_name=f"Rubrik_Degerlendirme_{len(selected_reports)}_Rapor.md",
                                mime="text/markdown",
                            )
                        except Exception as e:
                            st.error(f"Rubrik analizi hatası: {e}")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 5: Tutarsızlık Analizi
# ══════════════════════════════════════════════════════════════════════

with tabs[5]:
    st.header("🔍 Tutarsızlık Analizi")
    st.markdown("""
    Rapor verileri ile kullanıcı beyanlarını (anket + metin) karşılaştırarak her iddiayı 
    **DOĞRU / YANLIŞ / BİLGİ YOK** olarak etiketler.
    
    **Nasıl Çalışır:** Rapor içeriği **mutlak doğru** kabul edilir. Kullanıcı beyanları 
    (anket puanları ve metin iddiaları) rapor ile tek tek kıyaslanır.
    """)

    if not brain:
        st.error("Sistem başlatılamadı.")
    else:
        col1, col2 = st.columns([1, 1])
        
        with col1:
            proc_files = [f.name for f in Config.PROCESSED_DATA_DIR.glob("*.md")]
            selected_filename = st.selectbox("Kıyaslanacak Rapor", ["Tümü"] + proc_files)
            target_file = None if selected_filename == "Tümü" else selected_filename
            
            st.subheader("🤖 Otomatik Test Verisi Üretimi")
            st.caption("Rapordaki verilere dayanarak anket tablosu + metin beyanları üretir.")
            mode = st.radio("Üretilecek Veri Tipi", ["Tutarsız", "Tutarlı", "Karmaşık"], horizontal=True,
                           help="Tutarsız: Kasıtlı yanlış veriler içerir | Tutarlı: Rapor ile örtüşen veriler | Karmaşık: Karışık")
            
            if st.button("📋 Örnek Veri Üret"):
                if target_file and target_file != "Tümü":
                    with st.spinner("Örnek veri üretiliyor..."):
                        mock_data = brain.generate_mock_data(target_file, mode)
                        
                        # Regex ile BOLUM 1 ve BOLUM 2 ayrımı (Türkçe karakter ve başlık seviyesi bağımsız)
                        import re
                        parts = re.split(r'#{1,3}\s*B[OÖ]L[UÜ]M\s*2.*', mock_data, flags=re.IGNORECASE | re.DOTALL)
                        
                        if len(parts) > 1:
                            # Bölüm 1 temizle (Bölüm 1 başlığını kaldır)
                            b1_clean = re.sub(r'^#{1,3}\s*B[OÖ]L[UÜ]M\s*1.*', '', parts[0], flags=re.IGNORECASE).strip()
                            st.session_state["survey_text"] = b1_clean
                            st.session_state["comparison_text"] = parts[1].strip()
                        else:
                            st.session_state["comparison_text"] = mock_data
                            st.session_state["survey_text"] = ""
                        st.rerun()
                else:
                    st.warning("Lütfen veri üretmek için önce bir rapor seçin (Tümü seçeneği ile veri üretilemez).")

        with col2:
            st.subheader("📊 Anket Verileri")
            st.caption("Anket tablosunu aşağıya yapıştırın veya otomatik üretin.")
            survey_text = st.text_area(
                "Anket Tablosu",
                value=st.session_state.get("survey_text", ""),
                height=180,
                placeholder="| # | Soru | Puan (1-5) | İşaretleme |\n| 1 | ... | 4 | [X] |\n| 2 | ... | 3 | [X] |",
                key="survey_input",
            )

            st.subheader("📝 Metin Beyanları")
            st.caption("Metin iddialarını aşağıya yapıştırın veya otomatik üretin.")
            comparison_text = st.text_area(
                "Metin Beyanları",
                value=st.session_state.get("comparison_text", ""),
                height=180,
                placeholder="Birim bünyesinde 5 program bulunmakta olup, toplam 2441 öğrenci kayıtlıdır...\n3 adet TÜBİTAK projesi yürütülmektedir...",
                key="text_input",
            )

        if st.button("🔍 Doğrulama Analizini Başlat", type="primary"):
            if not comparison_text.strip() and not survey_text.strip():
                st.warning("Lütfen en az bir beyan girin (anket veya metin) veya otomatik üretin.")
            else:
                with st.spinner("Her iddia rapor ile tek tek karşılaştırılıyor..."):
                    try:
                        result = brain.check_consistency(
                            comparison_text=comparison_text.strip(),
                            survey_text=survey_text.strip() if survey_text.strip() else None,
                            filename=target_file,
                        )
                        
                        st.success("✅ Doğrulama Analizi Tamamlandı!")
                        st.markdown(result)
                        
                        st.download_button(
                            label="📥 Analiz Raporunu İndir (.md)",
                            data=result,
                            file_name=f"Dogrulama_Analizi_{selected_filename}.md",
                            mime="text/markdown",
                        )
                    except Exception as e:
                        st.error(f"Analiz hatası: {e}")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 5: Rapor Yönetimi
# ══════════════════════════════════════════════════════════════════════

with tabs[6]:
    st.header("📁 Rapor Yönetimi")
    # ... rest of the content remains mapped correctly to tabs ...
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
    st.markdown("### ⚠️ Boş / İçeriksiz İşlenmiş Dosyalar")
    if brain:
        empty_files = brain.processor.check_empty_processed_files()
        if empty_files:
            st.warning(f"{len(empty_files)} dosya boş veya yetersiz içerikli (genellikle görsel tabanlı PDF'ler):"
                       " Bu dosyalar için OCR ile yeniden işleme önerilir.")
            empty_df_data = [
                {
                    "Dosya": e["md_file"].name,
                    "Boyut (byte)": e["size"],
                    "Ham Dosya Mevcut": "✅" if e["raw_file"] else "❌",
                }
                for e in empty_files
            ]
            import pandas as pd
            st.dataframe(pd.DataFrame(empty_df_data), hide_index=True)

            if st.button("🔄 Boş Dosyaları OCR ile Yeniden İşle", type="primary"):
                with st.spinner("OCR ile yeniden işleniyor (görsel tabanlı PDF'ler için tesseract kullanılır)..."):
                    result = brain.reprocess_empty_files()
                    st.success(
                        f"✅ {result['yeniden_islenen']} dosya yeniden işlendi, "
                        f"{result['indekslenen_chunk']} chunk yeniden indekslendi."
                    )
                    st.cache_resource.clear()
                    st.rerun()
        else:
            st.success("✅ Tüm işlenmiş dosyalar yeterli içeriğe sahip.")

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
# SAYFA 7: Test Sonuçları
# ══════════════════════════════════════════════════════════════════════

with tabs[7]:
    st.header("📊 Test Sonuçları")
    st.markdown("""
    `python scripts/full_system_test.py` komutu ile çalıştırılan kapsamlı testlerin sonuçlarını gösterir.
    Sonuçlar `Data/test_results/` dizininde Markdown rapor olarak saklanır.
    """)

    import json
    # Markdown raporları listele
    test_md_files = sorted(
        Config.TEST_RESULTS_DIR.glob("test_raporu_*.md"),
        reverse=True
    ) if Config.TEST_RESULTS_DIR.exists() else []

    if not test_md_files:
        st.info(
            "Henüz test sonucu yok. Testi çalıştırmak için:\n\n"
            "`docker compose exec streamlit python scripts/full_system_test.py`"
        )
    else:
        selected_result = st.selectbox(
            "Test Raporu Seç",
            [f.name for f in test_md_files],
            key="test_result_select",
        )

        result_path = Config.TEST_RESULTS_DIR / selected_result

        # JSON özet bilgisini göster (varsa)
        json_name = selected_result.replace("test_raporu_", "test_results_").replace(".md", ".json")
        json_path = Config.TEST_RESULTS_DIR / json_name
        if json_path.exists():
            try:
                meta = json.loads(json_path.read_text(encoding="utf-8"))
                scol1, scol2, scol3 = st.columns(3)
                scol1.metric("📅 Tarih", meta.get("tarih", "—"))
                scol2.metric("✅ Başarılı", meta.get("basarili", 0))
                scol3.metric("⚠️ Hata", meta.get("hata", 0))
            except Exception:
                pass

        st.markdown("---")

        # Markdown raporunu göster
        try:
            md_content = result_path.read_text(encoding="utf-8")
            st.markdown(md_content)

            st.download_button(
                "📥 Raporu İndir (.md)",
                data=md_content,
                file_name=selected_result,
                mime="text/markdown",
            )
        except Exception as e:
            st.error(f"Rapor okunamadı: {e}")

# ══════════════════════════════════════════════════════════════════════
# SAYFA 8: Ayarlar
# ══════════════════════════════════════════════════════════════════════

with tabs[8]:
    st.header("⚙️ Ayarlar")
    if brain:
        status = brain.get_status()
        st.markdown("### 🔧 Yapılandırma")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Ollama URL:** `{status['ollama_url']}`")
            st.write(f"**Model:** `{status['model']}`")
            st.write(f"**Re-ranker:** `{status.get('reranker', 'bilinmiyor')}`")
        with col2:
            st.write(f"**Chunk Boyutu:** `{Config.CHUNK_SIZE}`")
            st.write(f"**Arama Sonuç (k):** `{Config.SEARCH_K}`")
            st.write(f"**Prompt Cache:** `{status.get('prompt_cache', 'bilinmiyor')}`")

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
