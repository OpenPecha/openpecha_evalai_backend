#!/usr/bin/env python3
"""
Clear alembic_version table to fix migration state
"""

def clear_alembic_version():
    """Clear the alembic_version table"""
    
    print("🔄 Attempting to clear alembic_version table...")
    
    # Try multiple methods to connect to database
    methods = [
        ("psycopg2", try_psycopg2),
        ("environment", try_env_connection),
        ("manual", show_manual_instructions)
    ]
    
    for method_name, method_func in methods:
        print(f"\n📋 Trying method: {method_name}")
        if method_func():
            print("✅ Successfully cleared alembic_version table!")
            return True
    
    return False

def try_psycopg2():
    """Try using psycopg2 directly"""
    try:
        import psycopg2
        
        # Try common connection parameters
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="openpecha",
            password="openpecha",  # Update if different
            database="eval_ai"
        )
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alembic_version")
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Cleared using psycopg2")
        return True
        
    except ImportError:
        print("❌ psycopg2 not available")
        return False
    except Exception as e:
        print(f"❌ psycopg2 connection failed: {e}")
        return False

def try_env_connection():
    """Try using environment database URL"""
    try:
        import os
        from urllib.parse import urlparse
        import psycopg2
        
        # Check for DATABASE_URL environment variable
        db_url = os.getenv('DATABASE_URL')
        if not db_url:
            # Try reading from alembic.ini
            try:
                with open('alembic.ini', 'r') as f:
                    for line in f:
                        if line.startswith('sqlalchemy.url'):
                            db_url = line.split('=', 1)[1].strip()
                            break
            except:
                pass
        
        if not db_url:
            print("❌ No database URL found")
            return False
        
        # Parse URL
        parsed = urlparse(db_url)
        
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username,
            password=parsed.password,
            database=parsed.path[1:] if parsed.path else None
        )
        
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alembic_version")
        conn.commit()
        cursor.close()
        conn.close()
        
        print("✅ Cleared using environment URL")
        return True
        
    except Exception as e:
        print(f"❌ Environment connection failed: {e}")
        return False

def show_manual_instructions():
    """Show manual instructions"""
    print("❌ Automatic methods failed")
    print("\n📋 MANUAL INSTRUCTIONS:")
    print("1. Connect to your PostgreSQL database using:")
    print("   - pgAdmin")
    print("   - DBeaver") 
    print("   - psql command line")
    print("   - Any other database tool")
    print("\n2. Run this SQL command:")
    print("   DELETE FROM alembic_version;")
    print("\n3. After clearing the table, run:")
    print("   alembic revision -m 'initial_schema'")
    print("   alembic revision --autogenerate -m 'sync_with_current_models'")
    print("   alembic upgrade head")
    
    return False

if __name__ == "__main__":
    print("🚀 Alembic Database State Cleaner")
    print("=" * 50)
    
    if clear_alembic_version():
        print("\n🎉 Success! Now run:")
        print("   alembic revision -m 'initial_schema'")
        print("   alembic revision --autogenerate -m 'sync_with_current_models'") 
        print("   alembic upgrade head")
    else:
        print("\n⚠️  Manual database clearing required")
        print("See FINAL_ALEMBIC_FIX.md for detailed instructions")
