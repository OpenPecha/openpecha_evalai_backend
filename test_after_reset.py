#!/usr/bin/env python3
"""
Test script to run after database reset is complete
"""

import subprocess
import sys

def test_alembic_after_reset():
    """Test that alembic works after database reset"""
    
    print("🧪 Testing Alembic functionality after reset...")
    
    tests = [
        ("alembic current", "Check current migration status"),
        ("alembic history", "Check migration history"), 
        ("alembic upgrade head", "Apply fresh start migration"),
        ("alembic current", "Verify migration applied"),
    ]
    
    for cmd, description in tests:
        print(f"\n📋 {description}")
        print(f"Running: {cmd}")
        
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ Success")
                if result.stdout.strip():
                    print(f"Output: {result.stdout.strip()}")
            else:
                print("❌ Failed")
                print(f"Error: {result.stderr.strip()}")
                return False
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            return False
    
    print("\n🎉 All tests passed! Ready for schema generation:")
    print("Next run: alembic revision --autogenerate -m 'sync_schema_with_current_models'")
    
    return True

if __name__ == "__main__":
    test_alembic_after_reset()
