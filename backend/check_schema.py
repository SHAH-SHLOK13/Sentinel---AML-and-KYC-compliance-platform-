import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
url = os.environ.get('SUPABASE_URL')
key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY')
sb = create_client(url, key)

# Check transactions count
tx = sb.table('transactions').select('id', count='exact').limit(0).execute()
print(f"Transactions: {tx.count}")

# Check alerts count
al = sb.table('alerts').select('id', count='exact').limit(0).execute()
print(f"Alerts: {al.count}")

# Check graph_cache
gc = sb.table('graph_cache').select('id, node_count, edge_count, cycles_found').execute()
if gc.data:
    for row in gc.data:
        print(f"Graph cache: {row}")
else:
    print("Graph cache: empty")

# Check model files exist
import os.path
models = ["backend/models/isolation_forest.pkl", "backend/models/user_profiles.pkl", "backend/models/user_histories.pkl"]
print("\nModel files:")
for m in models:
    exists = os.path.exists(m)
    size = os.path.getsize(m) / (1024*1024) if exists else 0
    print(f"  {'✅' if exists else '❌'} {m} ({size:.1f} MB)" if exists else f"  ❌ {m}")
