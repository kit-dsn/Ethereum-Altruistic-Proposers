import requests
import argparse
from sqlalchemy import create_engine, Boolean, String, MetaData, Table, Column, Index
from sqlalchemy.dialects.postgresql import insert
import pandas as pd

argparser = argparse.ArgumentParser()
argparser.add_argument('-d', '--database', default="postgresql://root@rfc.incus.tamedfox.eu/rfc")
argparser.add_argument('-t', '--table', default="accounts")

args = argparser.parse_args()

engine = create_engine(args.database)
connection = engine.connect()
def query(sql):
    return pd.read_sql(sql, connection)

EL_API_BASE = "http://localhost:8545"
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
    metadata = MetaData()
    
    columns = []

    for col_name, dtype in df.dtypes.items():
        if pd.api.types.is_bool_dtype(dtype):
            col_type = Boolean
        else:
            col_type = String

        if col_name == "coinbase_addr":
            columns.append(Column(col_name, col_type, unique=True))
        else:
            columns.append(Column(col_name, col_type))
    
    table = Table(DB_TABLE, 
                  metadata, 
                  *columns, 
                  Index(f"ix_{DB_TABLE}_coinbase_addr", "coinbase_addr")
        )
    
    metadata.create_all(engine, checkfirst=True)
    connection.execute(table.insert(), df.to_dict('records'))
    connection.commit()

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
