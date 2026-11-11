"""Synthetic banking demo data seeder. Run only against a disposable Supabase project."""
from __future__ import annotations
import os, uuid
from datetime import datetime,timedelta,timezone
import numpy as np
import pandas as pd
from dotenv import load_dotenv
load_dotenv()
def build_dataset(n_customers=1000,seed=42):
 rng=np.random.default_rng(seed); now=datetime.now(timezone.utc); customers=[]; tx=[]
 cohorts=np.array(["churn"]*200+["growth"]*300+["baseline"]*500); rng.shuffle(cohorts)
 for i,cohort in enumerate(cohorts):
  cid=str(uuid.uuid5(uuid.NAMESPACE_DNS,f"samora-demo-{seed}-{i}"))
  tier="Platinum" if cohort=="growth" and rng.random()<.45 else ("Gold" if rng.random()<.3 else "Standard")
  customers.append({"customer_id":cid,"full_name":f"Demo Customer {i+1:04d}","email":f"demo{i+1:04d}@example.test","account_tier":tier})
  balance=float(rng.uniform(7000,15000) if cohort=="growth" else rng.uniform(1000,5000))
  salary=float(rng.normal(4500 if cohort=="growth" else 2500,350))
  for day in range(365):
   date=now-timedelta(days=364-day); churn_window=cohort=="churn" and day>=305
   if date.day in (1,15) and not churn_window:
    amount=max(1000,salary*rng.uniform(.95,1.05)); balance+=amount
    tx.append(make_tx(cid,date+timedelta(hours=9),amount,"Credit","Salary","Mobile App",balance))
   prob=.55 if cohort=="growth" else (.45 if cohort=="baseline" else (.45 if not churn_window else .06))
   if rng.random()<prob:
    for _ in range(1+(rng.random()<.12)):
     category=(rng.choice(["Groceries","Travel","Luxury","Utilities","ATM"],p=[.25,.30,.22,.15,.08]) if cohort=="growth" else rng.choice(["Groceries","Travel","Luxury","Utilities","ATM","Transfers"],p=[.38,.08,.04,.25,.12,.13]))
     amount=float(rng.uniform(40,250) if category not in ("Travel","Luxury") else rng.uniform(180,900))
     balance=max(0,balance-amount)
     tx.append(make_tx(cid,date+timedelta(hours=int(rng.integers(7,22))),amount,"Debit",category,str(rng.choice(["Mobile App","Web","POS","ATM"])),balance))
  if cohort=="growth" and balance<5200:
   amount=5200-balance+float(rng.uniform(500,1500)); balance+=amount
   tx.append(make_tx(cid,now-timedelta(days=1),amount,"Credit","Transfers","Web",balance))
 return pd.DataFrame(customers),pd.DataFrame(tx)
def make_tx(cid,dt,amount,kind,category,channel,balance):
 tid=str(uuid.uuid5(uuid.NAMESPACE_URL,f"{cid}|{dt.isoformat()}|{amount:.2f}|{kind}|{category}|{channel}"))
 return {"transaction_id":tid,"customer_id":cid,"timestamp":dt.isoformat(),"amount":round(amount,2),"transaction_type":kind,"merchant_category":category,"channel":channel,"post_transaction_balance":round(balance,2)}
def seed(batch_size=500):
 from supabase import create_client
 url=os.getenv("SUPABASE_URL"); key=os.getenv("SUPABASE_SERVICE_ROLE_KEY")
 if not url or not key:raise RuntimeError("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
 if os.getenv("ALLOW_DEMO_SEEDING")!="true":raise RuntimeError("Set ALLOW_DEMO_SEEDING=true to confirm disposable demo database")
 db=create_client(url,key); customers,transactions=build_dataset()
 for df,table in ((customers,"customers"),(transactions,"transactions")):
  for start in range(0,len(df),batch_size):
   db.table(table).upsert(df.iloc[start:start+batch_size].to_dict("records"),on_conflict="customer_id" if table=="customers" else "transaction_id").execute()
 print(f"Seeded {len(customers)} demo customers and {len(transactions)} transactions")
 return {"customers_seeded":len(customers),"transactions_seeded":len(transactions)}
if __name__=="__main__":seed()
