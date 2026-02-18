from sqlalchemy import text
import sys
import os

# Add the current directory to sys.path so we can import app
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.db.session import engine

def migrate():
    print("Connecting to database to apply schema changes...")
    with engine.connect() as conn:
        # 1. Add is_google_user column
        print("Checking for 'is_google_user' column...")
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_google_user BOOLEAN DEFAULT FALSE"))
            conn.commit()
            print("Successfully added 'is_google_user' column.")
        except Exception as e:
            if "Duplicate column name" in str(e) or "1060" in str(e):
                print("'is_google_user' column already exists.")
            else:
                print(f"Error adding 'is_google_user': {e}")

        # 2. Also check and add OTP columns just in case they were missed
        columns_to_check = [
            ("otp", "VARCHAR(6)"),
            ("otp_expiry", "DATETIME"),
            ("is_verified", "BOOLEAN DEFAULT FALSE")
        ]
        
        for col_name, col_type in columns_to_check:
            print(f"Checking for '{col_name}' column...")
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                print(f"Successfully added '{col_name}' column.")
            except Exception as e:
                if "Duplicate column name" in str(e) or "1060" in str(e):
                    print(f"'{col_name}' column already exists.")
                else:
                    print(f"Error adding '{col_name}': {e}")

    print("Migration check complete.")

if __name__ == "__main__":
    migrate()
