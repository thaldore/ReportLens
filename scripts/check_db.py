import os
from langchain_community.vectorstores import Chroma
from langchain_ollama import OllamaEmbeddings

def check_db():
    embeddings = OllamaEmbeddings(model="llama3.1:8b")
    db_dir = "Data/vector_db"
    
    if not os.path.exists(db_dir):
        print(f"Hata: {db_dir} bulunamadı.")
        return

    db = Chroma(persist_directory=db_dir, embedding_function=embeddings)
    count = db._collection.count()
    print(f"Vektör veritabanındaki toplam parça (chunk) sayısı: {count}")

if __name__ == "__main__":
    check_db()
