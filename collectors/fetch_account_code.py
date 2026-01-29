import requests
import argparse
import duckdb
import pandas as pd

argparser = argparse.ArgumentParser()
argparser.add_argument('-d', '--database', default="/data/fast/historical_mempools/altrusitic_proposers/altrusitic_proposers.duckdb")
argparser.add_argument('-t', '--table', default="accounts")

args = argparser.parse_args()

conn = duckdb.connect(args.database)
def query(sql):
    return conn.execute(sql).df()

EL_API_BASE = "http://localhost:8504"
DB_TABLE = args.table


def fetch_account_data(addr):
    r = requests.post(
        EL_API_BASE,
        json={
            "method": "eth_getCode",
            "jsonrpc": "2.0",
            "id": 67,
            "params": [addr, "latest"]
        }
    )
    return r.json()["result"]

def upload_data(payload):
    df = pd.DataFrame(payload)
    
    # Create table if it doesn't exist
    try:
        conn.execute(f"CREATE TABLE IF NOT EXISTS {DB_TABLE} (coinbase_addr VARCHAR, is_account BOOLEAN, PRIMARY KEY (coinbase_addr))")
    except:
        pass
    
    # Use INSERT OR IGNORE for upsert behavior
    try:
        conn.insert(DB_TABLE, df)
    except:
        # If insert fails, it might be a duplicate, continue
        for _, row in df.iterrows():
            try:
                conn.execute(f"INSERT INTO {DB_TABLE} VALUES (?, ?)", [row['coinbase_addr'], row['is_account']])
            except:
                pass
    
    conn.commit()

# fetch all coinbase addresses
df_coinbase = query("""
    SELECT DISTINCT coinbase_addr FROM coinbase_blocks_all;
""")

accounts = []
uploaded = 0
for coinbase in df_coinbase['coinbase_addr']:
    data = fetch_account_data(coinbase)
    if data == '0x':
        accounts.append({
            "coinbase_addr": coinbase,
            "is_account": True
        })
    else:
        accounts.append({
            "coinbase_addr": coinbase,
            "is_account": False
        })
    
    if len(accounts) >= 100:
        upload_data(accounts)
        uploaded += len(accounts)
        print(f"Status: {uploaded} accounts uploaded")
        accounts = []

upload_data(accounts) # upload last set
uploaded += len(accounts)
print(f"Status: {uploaded} accounts uploaded.\nEnd.")
