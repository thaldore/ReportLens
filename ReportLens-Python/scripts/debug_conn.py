import pyodbc
from core.config import Config

def test_sa():
    print("Testing 'sa' login...")
    conn_str = (
        f"DRIVER={Config.MSSQL_DRIVER};"
        f"SERVER={Config.MSSQL_HOST};"
        f"DATABASE=master;"
        f"UID={Config.MSSQL_USER};"
        f"PWD={Config.MSSQL_PASS};"
        "TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str)
        print("✅ 'sa' login SUCCESS")
        conn.close()
    except Exception as e:
        print(f"❌ 'sa' login FAILED: {e}")

def test_windows_auth():
    print("\nTesting Windows Authentication...")
    conn_str = (
        f"DRIVER={Config.MSSQL_DRIVER};"
        f"SERVER={Config.MSSQL_HOST};"
        f"DATABASE=master;"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    try:
        conn = pyodbc.connect(conn_str)
        print("✅ Windows Auth SUCCESS")
        conn.close()
    except Exception as e:
        print(f"❌ Windows Auth FAILED: {e}")

if __name__ == "__main__":
    test_sa()
    test_windows_auth()
