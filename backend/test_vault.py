import asyncio
from app.lib.supabase import supabase
from app.services.aadhaar_vault import AadhaarVaultService

async def main():
    vault = AadhaarVaultService()
    
    print("Testing Vault Token Insertion...")
    
    # Get a real user ID
    res = supabase.table("users").select("id").limit(1).execute()
    if not res.data:
        print("No users in database to test with.")
        return
        
    user_id = res.data[0]["id"]
    print(f"Using real user ID: {user_id}")
    
    try:
        # 1. Store a test verification
        result = await vault.store_verification(
            user_id=user_id,
            vault_token="live_test_vault_token_xxxxx",
            verification_source="TEST_MOCK",
            verified_name="Test User",
            verified_dob="1990-01-01"
        )
        print(f"✅ Insert Successful. ID: {result.get('id')}")
        
        # 2. Check for duplicate
        is_dup = await vault.check_duplicate("live_test_vault_token_xxxxx")
        print(f"✅ Duplicate Check working: is_duplicate={is_dup}")
        
        # 3. Fetch verification
        fetch = await vault.get_user_verification(user_id)
        if fetch:
            print(f"✅ Fetch works. Vault token stored: {fetch.get('vault_token')}")
            
    except Exception as e:
        print(f"❌ Verification Database Test Failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
