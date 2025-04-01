import sqlite3
import datetime

DB_NAME = 'orna_data.db'

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create images table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            image_data BLOB NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create extracted_data table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS extracted_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            username TEXT NOT NULL,
            level INTEGER,
            class TEXT,
            friend INTEGER DEFAULT 0,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (image_id) REFERENCES images (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_image(file_path, image_data):
    """Adds an image to the database. Returns the image ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO images (file_path, image_data) VALUES (?, ?)", (file_path, image_data))
        image_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        # Image path already exists, find its ID
        cursor.execute("SELECT id FROM images WHERE file_path = ?", (file_path,))
        result = cursor.fetchone()
        image_id = result[0] if result else None
    except Exception as e:
        print(f"Error adding image: {e}")
        conn.rollback()
        image_id = None
    finally:
        conn.close()
    return image_id

def add_extracted_data(image_id, username, level, class_name, friend=False):
    """Adds extracted data linked to an image ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        # Convert boolean friend to integer (0 or 1) for DB
        friend_int = 1 if friend else 0 
        cursor.execute("INSERT INTO extracted_data (image_id, username, level, class, friend) VALUES (?, ?, ?, ?, ?)",
                       (image_id, username, level, class_name, friend_int))
        conn.commit()
    except Exception as e:
        print(f"Error adding extracted data: {e}")
        conn.rollback()
    finally:
        conn.close()

def clear_extracted_data_for_image(image_id):
    """Deletes all extracted data records associated with a specific image ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM extracted_data WHERE image_id = ?", (image_id,))
        conn.commit()
        print(f"Cleared existing data for image ID {image_id}")
    except Exception as e:
        print(f"Error clearing data for image {image_id}: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_all_extracted_data():
    """Retrieves all extracted data records along with image path."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        # Join extracted_data with images to get file_path
        cursor.execute("""
            SELECT d.id, d.image_id, i.file_path, d.username, d.level, d.class, d.friend, d.extracted_at 
            FROM extracted_data d
            JOIN images i ON d.image_id = i.id
            ORDER BY d.extracted_at DESC
        """)
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching extracted data: {e}")
        rows = []
    finally:
        conn.close()
    return rows

def get_extracted_data_by_image_id(image_id):
    """Retrieves all extracted data records for a specific image ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT username, level, class, friend 
            FROM extracted_data 
            WHERE image_id = ? 
            ORDER BY id ASC 
        """, (image_id,))
        # Fetch as list of dictionaries for easier use in GUI
        rows = [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error fetching extracted data for image {image_id}: {e}")
        rows = []
    finally:
        conn.close()
    return rows

def get_image_blob(image_id):
    """Retrieves the image blob data for a specific image ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT image_data FROM images WHERE id = ?", (image_id,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Error fetching image blob for image {image_id}: {e}")
        return None
    finally:
        conn.close()

def get_all_images():
    """Retrieves a list of all images (ID and file path) from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, file_path FROM images ORDER BY added_at DESC")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching all images: {e}")
        rows = []
    finally:
        conn.close()
    return rows

def delete_image_and_data(image_id):
    """Deletes an image and all its associated extracted data."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        # Delete associated extracted data first (due to foreign key constraint)
        cursor.execute("DELETE FROM extracted_data WHERE image_id = ?", (image_id,))
        # Delete the image itself
        cursor.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()
        print(f"Successfully deleted image ID {image_id} and its data.")
        return True
    except Exception as e:
        print(f"Error deleting image ID {image_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# Optional: Function to get image data by ID if needed later
# def get_image_data(image_id):
#     conn = sqlite3.connect(DB_NAME)
#     cursor = conn.cursor()
#     try:
#         cursor.execute("SELECT image_data FROM images WHERE id = ?", (image_id,))
#         result = cursor.fetchone()
#         return result[0] if result else None
#     except Exception as e:
#         print(f"Error fetching image data: {e}")
#         return None
#     finally:
#         conn.close() 