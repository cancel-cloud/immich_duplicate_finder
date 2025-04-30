import sqlite3
import json
from collections import Counter
from utility import is_running_in_container

data_path = 'data/' if is_running_in_container() else ''

############# DATABASE ###################

def startup_db_configurations():
    conn = sqlite3.connect('../data/settings.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            immich_server_url text,
            api_key text,
            images_folder text,
            timeout number
        )
    ''')
    # Default-Werte setzen, falls noch keine Zeile vorhanden
    c.execute('SELECT COUNT(*) FROM settings')
    if c.fetchone()[0] == 0:
        c.execute('''
            INSERT INTO settings (immich_server_url, api_key, images_folder, timeout)
            VALUES (?, ?, ?, ?)
        ''', ('', '', '', 2000))
    conn.commit()
    conn.close()

def load_settings_from_db():
    conn = sqlite3.connect('../data/settings.db')
    c = conn.cursor()
    c.execute("SELECT * FROM settings LIMIT 1")
    settings = c.fetchone()
    conn.close()
    return settings if settings else (None, None, None, None)

def save_settings_to_db(immich_server_url, api_key, images_folder, timeout):
    conn = sqlite3.connect('../data/settings.db')
    c = conn.cursor()
    c.execute("DELETE FROM settings")
    c.execute('''
        INSERT INTO settings (immich_server_url, api_key, images_folder, timeout)
        VALUES (?, ?, ?, ?)
    ''', (immich_server_url, api_key, images_folder, timeout))
    conn.commit()
    conn.close()

def bytes_to_megabytes(bytes_size):
    megabytes = bytes_size / (1024 * 1024)
    return f"{megabytes:.3f} MB"

####################### FAISS #############################

def startup_processed_duplicate_faiss_db():
    """Legt die Tabelle für Dubletten an, falls sie noch nicht existiert."""
    try:
        conn = sqlite3.connect(data_path + 'duplicates.db')
        cursor = conn.cursor()
        sql = '''CREATE TABLE IF NOT EXISTS duplicates(
           id INTEGER PRIMARY KEY,
           vector_id1 INT,
           vector_id2 INT,
           similarity FLOAT
        )'''
        cursor.execute(sql)
        conn.commit()
    except Exception as e:
        print("Error creating database/table:", e)
    finally:
        conn.close()

def save_duplicate_pair(vector_id1, vector_id2, similarity):
    similarity = float(similarity)
    try:
        conn = sqlite3.connect(data_path + 'duplicates.db')
        cursor = conn.cursor()
        # Prüfen, ob das Paar schon existiert
        cursor.execute(
            "SELECT * FROM duplicates WHERE (vector_id1 = ? AND vector_id2 = ?) OR (vector_id1 = ? AND vector_id2 = ?)",
            (vector_id1, vector_id2, vector_id2, vector_id1)
        )
        if cursor.fetchone():
            return
        # Neues Paar einfügen
        cursor.execute(
            "INSERT INTO duplicates (vector_id1, vector_id2, similarity) VALUES (?, ?, ?)",
            (vector_id1, vector_id2, similarity)
        )
        conn.commit()
    except Exception as e:
        print("Error inserting duplicate pair:", e)
    finally:
        conn.close()

def delete_duplicate_pair(asset_id_1, asset_id_2):
    try:
        conn = sqlite3.connect(data_path + 'duplicates.db')
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM duplicates WHERE (vector_id1 = ? AND vector_id2 = ?) OR (vector_id1 = ? AND vector_id2 = ?)",
            (asset_id_1, asset_id_2, asset_id_2, asset_id_1)
        )
        conn.commit()
        print("Deleted asset from db")
    except Exception as e:
        print(f"Error deleting duplicate entries for asset pair {asset_id_1}-{asset_id_2}:", e)
    finally:
        conn.close()

def load_duplicate_pairs(min_threshold, max_threshold):
    """Lädt alle Dubletten-Paare innerhalb gegebener Ähnlichkeitsschwellen."""
    try:
        conn = sqlite3.connect(data_path + 'duplicates.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT vector_id1, vector_id2 FROM duplicates
            WHERE similarity >= ? AND similarity <= ?
        """, (min_threshold, max_threshold))
        duplicates = cursor.fetchall()
        if not duplicates:
            print(f"No duplicates found within thresholds {min_threshold} and {max_threshold}")
        return duplicates
    except Exception as e:
        print("Error loading duplicates:", e)
        return []
    finally:
        if conn:
            conn.close()

def is_db_populated():
    """Prüft, ob die Duplikatentabelle Einträge enthält."""
    try:
        conn = sqlite3.connect(data_path + 'duplicates.db')
        cursor = conn.cursor()
        cursor.execute("SELECT EXISTS(SELECT 1 FROM duplicates LIMIT 1)")
        exists = cursor.fetchone()[0]
        return exists == 1
    except Exception as e:
        print("Error checking database population:", e)
        return False
    finally:
        if conn:
            conn.close()

def remove_deleted_assets_from_db(deleted_asset_ids):
    """Entfernt alle Duplikateneinträge, die gelöschte Assets enthalten."""
    try:
        conn = sqlite3.connect(data_path + 'duplicates.db')
        cursor = conn.cursor()
        placeholders = ', '.join('?' for _ in deleted_asset_ids)
        query = f'''
            DELETE FROM duplicates
            WHERE vector_id1 IN ({placeholders}) OR vector_id2 IN ({placeholders})
        '''
        params = deleted_asset_ids + deleted_asset_ids
        cursor.execute(query, params)
        conn.commit()
    except Exception as e:
        print("Error removing deleted assets from duplicates db:", e)
    finally:
        conn.close()