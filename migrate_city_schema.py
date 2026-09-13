"""
Idempotent Safe SQLite Migration Script
Adds 'city' to 'users' table and 'pickup_city' to 'surplus_listings' table.
Preserves all existing data, does not drop or reseed tables.
Assigns sensible cities only to existing demo accounts where known:
  - kitchen_demo, admin, ngo_demo, feeding_india -> 'Delhi'
  - Demo3, abc -> 'Rajkot'
Derives surplus_listings.pickup_city from its donor's city where available.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'database.sqlite')

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}. Skipping.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Check users table
        cursor.execute("PRAGMA table_info(users)")
        user_cols = [col[1] for col in cursor.fetchall()]
        if 'city' not in user_cols:
            print("Adding column 'city' (VARCHAR(64)) to table 'users'...")
            cursor.execute("ALTER TABLE users ADD COLUMN city VARCHAR(64)")
            print("Successfully added 'city' to 'users'.")
        else:
            print("Column 'city' already exists in 'users'.")

        # 2. Check surplus_listings table
        cursor.execute("PRAGMA table_info(surplus_listings)")
        listing_cols = [col[1] for col in cursor.fetchall()]
        if 'pickup_city' not in listing_cols:
            print("Adding column 'pickup_city' (VARCHAR(64)) to table 'surplus_listings'...")
            cursor.execute("ALTER TABLE surplus_listings ADD COLUMN pickup_city VARCHAR(64)")
            print("Successfully added 'pickup_city' to 'surplus_listings'.")
        else:
            print("Column 'pickup_city' already exists in 'surplus_listings'.")

        # 3. Assign cities only to known existing demo accounts
        # Delhi demo accounts
        cursor.execute("""
            UPDATE users
            SET city = 'Delhi'
            WHERE username IN ('kitchen_demo', 'admin', 'ngo_demo', 'feeding_india')
              AND (city IS NULL OR city = '')
        """)
        print(f"Updated Delhi demo accounts: {cursor.rowcount} rows affected.")

        # Rajkot demo accounts
        cursor.execute("""
            UPDATE users
            SET city = 'Rajkot'
            WHERE username IN ('Demo3', 'abc')
              AND (city IS NULL OR city = '')
        """)
        print(f"Updated Rajkot demo accounts: {cursor.rowcount} rows affected.")

        # 4. Derive pickup_city for listings with NULL pickup_city from donor's city
        cursor.execute("""
            UPDATE surplus_listings
            SET pickup_city = (
                SELECT city FROM users WHERE users.id = surplus_listings.donor_id
            )
            WHERE (pickup_city IS NULL OR pickup_city = '')
              AND EXISTS (
                  SELECT 1 FROM users WHERE users.id = surplus_listings.donor_id AND users.city IS NOT NULL AND users.city != ''
              )
        """)
        print(f"Derived pickup_city for listings from donor city: {cursor.rowcount} rows affected.")

        conn.commit()
        print("Migration committed successfully!")

        # Verify results
        print("\n--- Current Users & Cities ---")
        cursor.execute("SELECT id, username, role, city, address FROM users")
        for row in cursor.fetchall():
            print(row)

        print("\n--- Current Surplus Listings Sample & Pickup Cities ---")
        cursor.execute("SELECT id, food_name, donor_id, pickup_city, pickup_address FROM surplus_listings LIMIT 5")
        for row in cursor.fetchall():
            print(row)

        cursor.execute("SELECT COUNT(*), COUNT(pickup_city) FROM surplus_listings")
        print(f"Total listings: {cursor.fetchone()}")

    except Exception as e:
        conn.rollback()
        print(f"Error during migration: {e}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
