import os
import logging
from pathlib import Path
from agno.agent import Agent
from agno.models.ollama import Ollama
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Log ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class QualityBrain:
    def __init__(self, processed_dir: str, vector_db_dir: str):
        self.processed_dir = Path(processed_dir)
        self.vector_db_dir = Path(vector_db_dir)
        
        # Docker/Sunucu uyumu için URL yapılandırması
        self.ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        self.embeddings = OllamaEmbeddings(
            model="nomic-embed-text", 
            base_url=self.ollama_url
        )
        self.model = Ollama(
            id="llama3.1:8b", 
            host=self.ollama_url
        )
        self.vector_store = None
        
        # Vektör DB dizinini oluştur
        self.vector_db_dir.mkdir(parents=True, exist_ok=True)

    def index_documents(self):
        """Markdown dosyalarını vektör veritabanına indeksler."""
        logger.info(f"Dizin taranıyor: {self.processed_dir}")
        md_files = list(self.processed_dir.glob("**/*.md"))
        logger.info(f"Bulunan Markdown dosyası sayısı: {len(md_files)}")
        
        if not md_files:
            logger.error("İndekslenecek dosya bulunamadı!")
            return

        logger.info("Belgeler yükleniyor...")
        loader = DirectoryLoader(str(self.processed_dir), glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
        documents = loader.load()
        logger.info(f"{len(documents)} döküman yüklendi.")
        
        if not documents:
            logger.error("Döküman içeriği boş!")
            return

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(documents)
        logger.info(f"{len(splits)} parçaya bölündü. Vektörleştirme başlatılıyor (bu işlem zaman alabilir)...")
        
        self.vector_store = Chroma.from_documents(
            documents=splits,
            embedding=self.embeddings,
            persist_directory=str(self.vector_db_dir)
        )
        logger.info("Vektör veritabanı başarıyla oluşturuldu ve kaydedildi.")

    def get_search_tool(self):
        """Ajanların kullanımı için arama fonksiyonu döner."""
        def search_reports(sorgu: str) -> str:
            """Üniversite kalite raporları veritabanında arama yapar ve ilgili metinleri döner."""
            if not self.vector_store:
                self.vector_store = Chroma(persist_directory=str(self.vector_db_dir), embedding_function=self.embeddings)
            
            # Daha geniş bir arama için k=8 yapalım
            results = self.vector_store.similarity_search(sorgu, k=8)
            context = "\n\n---\n\n".join([doc.page_content for doc in results])
            logger.info(f"Arama yapıldı: {sorgu} - {len(results)} sonuç bulundu.")
            return context
        
        return search_reports

    def create_agents(self):
        """Kalite Analiz Uzmanı ajanını oluşturur."""
        search_tool = self.get_search_tool()

        # Kalite Analiz Uzmanı
        self.expert = Agent(
            name="Kalite Analiz Uzmanı",
            model=self.model,
            instructions=[
                "Sen 'ReportLens' projesi için özelleştirilmiş bir 'Üniversite Kalite ve Strateji Analiz Uzmanı'sın.",
                "Görevin, üniversite akademik birimlerinin raporlarını analiz etmektir.",
                "1. Veri Odaklılık: Sadece sana sunulan gerçek verilere dayanarak konuş.",
                "2. Karşılaştırmalı Yaklaşım: Yıllar arasındaki değişimleri vurgula.",
                "3. Tablo Analizi: Sayısal verileri yorumla.",
                "4. Akademik Dil: Profesyonel ve yapıcı bir Türkçe kullan."
            ],
            tools=[search_tool]
        )

    def analyze(self, query: str):
        """Analiz sürecini başlatır."""
        return self.expert.run(query)

if __name__ == "__main__":
    PROCESSED_DATA = "Data/processed"
    VECTOR_DB = "Data/vector_db"
    
    brain = QualityBrain(PROCESSED_DATA, VECTOR_DB)
    # İlk çalıştırmada indeksle
    brain.index_documents()
    
    brain.create_agents()
    # Örnek sorgu
    logger.info("Analiz başlatılıyor...")
    response = brain.analyze("Fen fakültesinin 2019-2024 arası gelişimini özetle.")
    print(response.content)
