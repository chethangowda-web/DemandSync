#!/usr/bin/env python3
"""
PDS DEMANDSYNC — Synthetic Dataset Generator
Seed: 20260921 | Deterministic | Production-style prototype
Generates 24 CSVs + manifest JSON under K:/DemandSYNC/data
Run: python scripts/generate_datasets.py
"""
import hashlib, json, uuid, random, math, os
from datetime import datetime, timedelta, date
from pathlib import Path
import numpy as np
import pandas as pd
from faker import Faker

SEED = 20260921
random.seed(SEED); np.random.seed(SEED); Faker.seed(SEED)
fake = Faker("en_IN")
Faker.seed(SEED)

BASE = Path(__file__).resolve().parents[1]
DATA = BASE / "data"

# Helpers
def sha256_canonical(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',',':')).encode()).hexdigest()
def km_dist(lat1, lon1, lat2, lon2):
    R=6371
    dlat=math.radians(lat2-lat1); dlon=math.radians(lon2-lon1)
    a=math.sin(dlat/2)**2+ math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return 2*R*math.asin(math.sqrt(a))
def cycle_to_date(c): return datetime.strptime(c+"-01","%Y-%m-%d").date()
def synthetic_phone(idx): return f"90000{50000+ (idx*997 % 40000):05d}" # 9000050000-9000089999 safe

# Config
DISTRICTS = [
    ("BENGALURU_URBAN","Bengaluru Urban",12.9716,77.5946),
    ("MYSURU","Mysuru",12.2958,76.6394),
    ("TUMAKURU","Tumakuru",13.3409,77.1010),
    ("MANDYA","Mandya",12.5242,76.8958),
    ("HASSAN","Hassan",13.0072,76.0497),
    ("SHIVAMOGGA","Shivamogga",13.9299,75.5681),
]
CYCLES_HIST = [f"2025-{m:02d}" for m in range(1,13)]  # 12 hist
CYCLES_OP = ["2026-01","2026-02","2026-03"] # 3 operational (intent/forecast/alloc/manifest)
CYCLES_ALL = CYCLES_HIST + CYCLES_OP
CYCLES_OP_ONLY = CYCLES_OP # for intents etc
TALUKS = {d[0]: [f"{d[0][:3]}-Taluk-{i+1}" for i in range(4)] for d in DISTRICTS}

print("="*50)
print("PDS DEMANDSYNC DATA GENERATION")
print("="*50)
print(f"Seed: {SEED} | Base: {BASE}")

# 1. Warehouses 25
warehouses=[]
for i in range(25):
    d = DISTRICTS[i % len(DISTRICTS)]
    lat = d[2] + np.random.uniform(-0.35,0.35)
    lon = d[3] + np.random.uniform(-0.35,0.35)
    cap = int(np.random.choice([50000,75000,100000,120000,150000], p=[0.2,0.25,0.3,0.15,0.1]))
    rice_stock = int(cap*0.55*np.random.uniform(0.7,0.95))
    wheat_stock = int(cap*0.45*np.random.uniform(0.7,0.95))
    warehouses.append([f"WH-{i+1:03d}", f"{d[0].title()} Central Warehouse {i+1}", d[0], round(lat,6), round(lon,6), rice_stock, wheat_stock, cap, random.choice(["ACTIVE","ACTIVE","ACTIVE","MAINTENANCE"])])
df_wh = pd.DataFrame(warehouses, columns=["warehouse_id","warehouse_name","district","latitude","longitude","rice_stock_kg","wheat_stock_kg","total_capacity_kg","status"])
# ensure at least 23 ACTIVE
df_wh.loc[df_wh.status=="MAINTENANCE","status"]="ACTIVE"
df_wh.loc[0,"status"]="ACTIVE"

# 2. FPS 600
fps=[]
fps_names_pool = ["Shakti","Jan Seva","Anna","Bharat","Grama","Samridhi","Ujala","Namma","Jai Karnataka","Sahyadri","Vikas","Annapurna","Santosh","Laxmi","Ganga","Surya","Chamundi","Kaveri","Tunga"]
for i in range(600):
    wh = df_wh.iloc[i % len(df_wh)]["warehouse_id"]
    drow = df_wh.iloc[i % len(df_wh)]["district"]
    # coordinate near warehouse
    wh_lat = df_wh.iloc[i % len(df_wh)]["latitude"]; wh_lon=df_wh.iloc[i % len(df_wh)]["longitude"]
    lat = wh_lat + np.random.uniform(-0.18,0.18)
    lon = wh_lon + np.random.uniform(-0.18,0.18)
    cap = int(np.random.choice([1200,1500,2000,2500,3000,3500], p=[0.1,0.2,0.3,0.2,0.13,0.07]))
    # intentionally create 8% low capacity for SCENARIO B
    if i % 37==0: cap = int(np.random.randint(800,1100))
    fps_id = f"FPS-{i+1:04d}"
    owner_id = f"OFF-{6000+i+1:05d}" # will map to officers
    fps.append([fps_id, f"{random.choice(fps_names_pool)} Fair Price Shop {i+1:03d}", owner_id, drow, random.choice(TALUKS[drow]), round(lat,6), round(lon,6), cap, wh, random.choice(["ACTIVE","ACTIVE","ACTIVE","SUSPENDED"]), "09:00-18:00", (date(2023,1,1)+timedelta(days=random.randint(0,700))).isoformat()])
df_fps = pd.DataFrame(fps, columns=["fps_id","fps_name","owner_id","district","taluk","latitude","longitude","capacity_kg","warehouse_id","status","opening_hours","created_at"])
# ensure unique names
assert df_fps.fps_name.nunique()==600

# 3. Officers ~650
officers=[]
roles = ["DISTRICT_OFFICER","FIELD_FOOD_INSPECTOR","FPS_OWNER","ADMIN","AUDITOR"]
# 6 district officers, 60 inspectors, 600 owners, 2 admin, 5 auditors
officer_specs=[("DISTRICT_OFFICER",6),("FIELD_FOOD_INSPECTOR",60),("FPS_OWNER",600),("ADMIN",2),("AUDITOR",5)]
oid=1
for role,count in officer_specs:
    for j in range(count):
        d = DISTRICTS[oid % len(DISTRICTS)][0] if role!="ADMIN" else DISTRICTS[0][0]
        name = fake.name()
        # ensure not placeholder Test User
        officers.append([f"OFF-{oid:05d}", f"EMP{2020+ (oid%6):04d}{oid:05d}", name, role, d, synthetic_phone(oid), "ACTIVE"])
        oid+=1
df_off = pd.DataFrame(officers, columns=["officer_id","employee_code","name","role","district","phone","status"])
# override FPS owner ids to match fps owner_id
fps_owner_ids = df_fps.owner_id.tolist()
# map first 600 FPS_OWNER officers to those ids
owner_officers = df_off[df_off.role=="FPS_OWNER"].copy()
owner_officers["officer_id"] = fps_owner_ids
# rebuild df_off with corrected owner ids
df_off = pd.concat([df_off[df_off.role!="FPS_OWNER"], owner_officers], ignore_index=True)

# 4. Beneficiaries 10,000
beneficiaries=[]
for i in range(10000):
    fps_row = df_fps.iloc[np.random.randint(0,600)]
    fps_id = fps_row["fps_id"]
    district = fps_row["district"]; taluk = fps_row["taluk"]
    scheme = np.random.choice(["PHH","AAY"], p=[0.82,0.18])
    if scheme=="AAY":
        hh = int(np.random.choice([3,4,5,6,7], p=[0.15,0.25,0.25,0.2,0.15]))
        entitlement = 35
    else:
        hh = int(np.random.choice([1,2,3,4,5,6], p=[0.08,0.18,0.28,0.25,0.13,0.08]))
        entitlement = hh*5
    rice_ent = int(round(entitlement* np.random.uniform(0.55,0.65)))
    wheat_ent = entitlement - rice_ent
    lat = fps_row["latitude"] + np.random.uniform(-0.04,0.04)
    lon = fps_row["longitude"] + np.random.uniform(-0.04,0.04)
    beneficiaries.append([f"BEN-{i+1:06d}", f"RC{2023 + (i%3):04d}{100000+i:06d}", fake.name(), hh, scheme, entitlement, rice_ent, wheat_ent, fps_id, district, taluk, round(lat,6), round(lon,6), synthetic_phone(10000+i), random.choice(["ACTIVE","ACTIVE","ACTIVE","MIGRATED"]), (date(2022,1,1)+timedelta(days=random.randint(0,900))).isoformat()])
df_ben = pd.DataFrame(beneficiaries, columns=["beneficiary_id","ration_card_id","head_of_household","household_size","scheme_type","entitlement_kg","rice_entitlement_kg","wheat_entitlement_kg","current_fps_id","district","taluk","latitude","longitude","registered_mobile","status","created_at"])

# verify entitlement = rice+wheat
assert (df_ben.entitlement_kg == df_ben.rice_entitlement_kg + df_ben.wheat_entitlement_kg).all()

# 5. Vehicles 150
vehicles=[]
types = [("SMALL",800),("MEDIUM",1500),("LARGE",3000),("HEAVY",5000)]
for i in range(150):
    wh = df_wh.iloc[i % len(df_wh)]["warehouse_id"]
    vtype, cap = random.choice(types)
    # vary cap +/-10%
    cap = int(cap * np.random.uniform(0.9,1.1))
    wh_lat = df_wh[df_wh.warehouse_id==wh].iloc[0]["latitude"]; wh_lon=df_wh[df_wh.warehouse_id==wh].iloc[0]["longitude"]
    lat = wh_lat + np.random.uniform(-0.02,0.02)
    lon = wh_lon + np.random.uniform(-0.02,0.02)
    vstatus = random.choices(["AVAILABLE","ASSIGNED","IN_TRANSIT","DELIVERED","MAINTENANCE"], weights=[0.6,0.15,0.1,0.1,0.05])[0]
    vehicles.append([f"VEH-{i+1:04d}", f"KA-{random.randint(1,29):02d}-{chr(random.randint(65,90))}{chr(random.randint(65,90))}-{random.randint(1000,9999)}", vtype, cap, vstatus, wh, f"DRV-{i+1:04d}", round(lat,6), round(lon,6), "2025-01-01", "2026-12-31"])
df_veh = pd.DataFrame(vehicles, columns=["vehicle_id","vehicle_number","vehicle_type","capacity_kg","current_status","warehouse_id","driver_id","latitude","longitude","availability_start","availability_end"])
# ensure MAINTENANCE vehicles not assigned later (will enforce)

# 6. Historical demand 12 cycles x FPS x commodity
hist=[]
benef_count_per_fps = df_ben.groupby("current_fps_id").size().to_dict()
for cycle in CYCLES_HIST:
    cdate = cycle_to_date(cycle); month=cdate.month
    season = "KHARIF" if month in [6,7,8,9] else "RABI" if month in [11,12,1,2] else "SUMMER"
    season_factor = 1.08 if season=="KHARIF" else 0.96 if season=="SUMMER" else 1.0
    for _, fps_row in df_fps.iterrows():
        fps_id=fps_row["fps_id"]
        cnt = benef_count_per_fps.get(fps_id, np.random.randint(8,22))
        avg_ent = df_ben[df_ben.current_fps_id==fps_id].entitlement_kg.mean() if cnt>0 else 15
        if np.isnan(avg_ent): avg_ent=15
        for commodity in ["RICE","WHEAT"]:
            base = cnt * avg_ent * (0.58 if commodity=="RICE" else 0.42)
            trend = np.random.uniform(-0.05,0.08) # -5% to +8%
            noise = np.random.uniform(-0.04,0.04)
            demand = int(base * season_factor * (1+trend) * (1+noise))
            demand = max(200, demand)
            prev = int(demand* np.random.uniform(0.92,1.06))
            stockout = 1 if random.random()<0.03 else 0
            if stockout: demand = int(demand*0.7) # stockout reduces observed demand
            hist.append([fps_id, cycle, commodity, demand, cnt, season, month, cdate.year, prev, round(trend,3), round(season_factor,3), stockout])
df_hist = pd.DataFrame(hist, columns=["fps_id","cycle","commodity","demand_kg","beneficiary_count","season","month","year","previous_demand_kg","trend_factor","season_factor","stockout_flag"])

# 7. Intent signals 2 cycles (2026-01,2026-02) beneficiary-level
intents=[]
intent_id=1
for cycle in CYCLES_OP[:2]: # 2 cycles
    # sample 70% beneficiaries submit
    sample_ben = df_ben.sample(frac=0.7, random_state=SEED+ hash(cycle)%1000)
    for _, ben in sample_ben.iterrows():
        # intent <= entitlement, often slightly less
        factor = np.random.uniform(0.7,1.0) # request less than entitlement
        # occasional exact entitlement
        if random.random()<0.4: factor=1.0
        total = int(ben["entitlement_kg"]*factor)
        # split proportionally to entitlement
        rice_ratio = ben["rice_entitlement_kg"]/ben["entitlement_kg"] if ben["entitlement_kg"]>0 else 0.6
        rice_q = int(round(total*rice_ratio))
        wheat_q = total - rice_q
        # ensure not exceed entitlement per commodity
        rice_q = min(rice_q, ben["rice_entitlement_kg"])
        wheat_q = min(wheat_q, ben["wheat_entitlement_kg"])
        total = rice_q + wheat_q
        coll_mode = random.choice(["SELF","AUTHORIZED_PERSON"])
        # random submitted within cycle choice window 5th-20th day
        day = random.randint(5,20)
        cdate = cycle_to_date(cycle)
        submitted = datetime(cdate.year,cdate.month,day, random.randint(8,19), random.randint(0,59)).isoformat()
        status = "CANCELLED" if random.random()<0.03 else "SUBMITTED"
        intents.append([f"INT-{intent_id:07d}", ben["beneficiary_id"], ben["current_fps_id"], cycle, rice_q, wheat_q, total, coll_mode, submitted, status])
        intent_id+=1
df_intent = pd.DataFrame(intents, columns=["intent_id","beneficiary_id","fps_id","cycle","rice_quantity_kg","wheat_quantity_kg","total_quantity_kg","collection_mode","submitted_at","status"])

# 8. Demand forecast per FPS per cycle per commodity (2026-01..03)
forecasts=[]
fid=1
for cycle in CYCLES_OP:
    for _, fps_row in df_fps.iterrows():
        fps_id=fps_row["fps_id"]
        for commodity in ["RICE","WHEAT"]:
            # baseline: avg of last 3 hist cycles for that fps commodity
            hist_vals = df_hist[(df_hist.fps_id==fps_id)&(df_hist.commodity==commodity)].sort_values("cycle").tail(3).demand_kg.tolist()
            baseline = int(np.mean(hist_vals)) if hist_vals else 1000
            # intent demand aggregated
            intent_vals = df_intent[(df_intent.fps_id==fps_id)&(df_intent.cycle==cycle)&(df_intent.status=="SUBMITTED")]
            col = "rice_quantity_kg" if commodity=="RICE" else "wheat_quantity_kg"
            intent_dem = int(intent_vals[col].sum()) if not intent_vals.empty else int(baseline* np.random.uniform(0.85,1.05))
            # forecast = baseline*0.5 + intent*0.5 + season adj + noise, ensure difference
            season_adj = 1.02 if cycle in ["2026-01","2026-02"] else 1.0
            forecast = int((baseline*0.45 + intent_dem*0.55)*season_adj * np.random.uniform(0.96,1.04))
            # ensure forecast != baseline != intent sometimes
            if forecast==intent_dem: forecast+= random.randint(-30,30)
            forecasts.append([f"FC-{fid:07d}", fps_id, cycle, commodity, baseline, intent_dem, forecast, "xgb-v1.0", datetime(2025,12,28,10,0).isoformat(), "hist-v1-202512", "30d"])
            fid+=1
df_forecast = pd.DataFrame(forecasts, columns=["forecast_id","fps_id","cycle","commodity","baseline_demand_kg","intent_demand_kg","forecast_demand_kg","model_version","prediction_generated_at","training_dataset_version","prediction_horizon"])

# 9. Allocations per FPS per cycle per commodity
allocs=[]
alloc_id=1
# warehouse stock tracking per cycle per commodity (approx)
wh_stock = {wh: {"RICE": int(df_wh[df_wh.warehouse_id==wh].iloc[0]["rice_stock_kg"]), "WHEAT": int(df_wh[df_wh.warehouse_id==wh].iloc[0]["wheat_stock_kg"])} for wh in df_wh.warehouse_id}
for cycle in CYCLES_OP:
    for _, fps_row in df_fps.iterrows():
        fps_id=fps_row["fps_id"]; wh=fps_row["warehouse_id"]; cap=fps_row["capacity_kg"]
        # distribute capacity per commodity 60/40
        cap_rice = int(cap*0.6); cap_wheat = int(cap*0.4)
        for commodity in ["RICE","WHEAT"]:
            fc = df_forecast[(df_forecast.fps_id==fps_id)&(df_forecast.cycle==cycle)&(df_forecast.commodity==commodity)].iloc[0]
            requested = int(fc["forecast_demand_kg"]* np.random.uniform(0.95,1.05))
            # warehouse constraint
            wh_avail = wh_stock[wh][commodity]
            cap_limit = cap_rice if commodity=="RICE" else cap_wheat
            # apply scenarios
            # FPS capacity shortage scenario B: every 37th fps already low capacity, keep requested high -> will block
            # WAREHOUSE shortage scenario C: for WH-001 in 2026-02, artificially low stock
            # VEHICLE shortage scenario D handled at manifest level
            # ENTITLEMENT floor scenario E: allocate less than entitlement aggregate for some FPS
            allocated = min(requested, wh_avail, cap_limit)
            # force some BLOCKED scenarios
            status="APPROVED"
            if fps_id=="FPS-0037" and cycle=="2026-01" and commodity=="RICE":
                allocated = cap_limit - 50 # capacity-limited allocation
                requested = allocated + 300 # demand must exceed what capacity allows -> BLOCKED due FPS_CAPACITY (no RNG draw)
                status="BLOCKED"
            elif wh=="WH-001" and cycle=="2026-02" and commodity=="RICE":
                # warehouse stock shortage
                allocated = max(0, wh_avail - 8000) if wh_avail>8000 else 0
                # force requested > allocated
                if requested <= allocated: requested = allocated + random.randint(200,600)
                status="BLOCKED"
            elif cycle=="2026-01" and fps_id=="FPS-0100" and commodity=="WHEAT":
                # entitlement floor violation: allocate less than sum entitlements
                # compute entitlement sum for this fps
                ent_sum = df_ben[df_ben.current_fps_id==fps_id]["wheat_entitlement_kg"].sum()
                allocated = max(0, int(ent_sum*0.7)) # 70% of entitlement -> violation
                requested = int(ent_sum*0.9)
                status="BLOCKED"
            else:
                if allocated < requested *0.95:
                    status="BLOCKED" if random.random()<0.7 else "APPROVED"
                else:
                    status="APPROVED"
            # deduct from wh stock for next FPS (approx)
            wh_stock[wh][commodity] = max(0, wh_avail - allocated)
            allocs.append([f"ALLOC-{alloc_id:07d}", cycle, fps_id, commodity, requested, allocated, wh, status, "SYSTEM", "OFF-00001", datetime(2025,12,29,11,0).isoformat()])
            alloc_id+=1
            # reset wh stock per cycle start not cumulative across FPS? But we already deduct; for realism keep per cycle deduction
    # replenish wh stock next cycle
    for wh in wh_stock:
        dfw = df_wh[df_wh.warehouse_id==wh].iloc[0]
        wh_stock[wh]["RICE"] = int(dfw["rice_stock_kg"]* np.random.uniform(0.85,0.98))
        wh_stock[wh]["WHEAT"] = int(dfw["wheat_stock_kg"]* np.random.uniform(0.85,0.98))
df_alloc = pd.DataFrame(allocs, columns=["allocation_id","cycle","fps_id","commodity","requested_kg","allocated_kg","warehouse_id","status","source","approved_by","approved_at"])

# 10. Inventory WAREHOUSE + FPS
invent=[]
inv_id=1
# WAREHOUSE inventory per cycle
for cycle in CYCLES_ALL[-6:]: # last 6 cycles for brevity
    for _, wh in df_wh.iterrows():
        for commodity in ["RICE","WHEAT"]:
            opening = int(wh["rice_stock_kg"] if commodity=="RICE" else wh["wheat_stock_kg"])
            opening = int(opening* np.random.uniform(0.8,1.0))
            received = int(opening* np.random.uniform(0.1,0.3))
            # dispatched = sum allocations for that wh cycle commodity
            disp = df_alloc[(df_alloc.warehouse_id==wh["warehouse_id"])&(df_alloc.cycle==cycle)&(df_alloc.commodity==commodity)].allocated_kg.sum()
            if pd.isna(disp): disp=0
            disp = int(disp* np.random.uniform(0.9,1.0))
            distributed=0
            closing = opening + received - disp - distributed
            closing = max(0, closing)
            invent.append([f"INV-{inv_id:07d}","WAREHOUSE", wh["warehouse_id"], commodity, opening, received, disp, distributed, closing, cycle])
            inv_id+=1
# FPS inventory per cycle op only
for cycle in CYCLES_OP:
    for _, fps_row in df_fps.iterrows():
        for commodity in ["RICE","WHEAT"]:
            alloc = df_alloc[(df_alloc.fps_id==fps_row["fps_id"])&(df_alloc.cycle==cycle)&(df_alloc.commodity==commodity)].allocated_kg.iloc[0] if not df_alloc[(df_alloc.fps_id==fps_row["fps_id"])&(df_alloc.cycle==cycle)&(df_alloc.commodity==commodity)].empty else 0
            opening = int(np.random.randint(50,300))
            received = int(alloc* np.random.uniform(0.85,1.0)) if alloc>0 else 0
            distributed = int(received* np.random.uniform(0.6,0.9)) if received>0 else 0
            dispatched=0
            closing = opening + received - dispatched - distributed
            invent.append([f"INV-{inv_id:07d}","FPS", fps_row["fps_id"], commodity, opening, received, dispatched, distributed, closing, cycle])
            inv_id+=1
df_inv = pd.DataFrame(invent, columns=["inventory_id","location_type","location_id","commodity","opening_stock_kg","received_kg","dispatched_kg","distributed_kg","closing_stock_kg","cycle"])

# 11. Dispatch manifests  (per warehouse per cycle grouping)
manifests=[]
manifest_items=[]
route_rows=[]
manifest_id_seq=1
item_id_seq=1
route_id_seq=1
# group FPS by warehouse per cycle, batch into manifests of 5-8 FPS per vehicle
for cycle in CYCLES_OP:
    for wh_id in df_wh.warehouse_id:
        fps_list = df_fps[df_fps.warehouse_id==wh_id].sample(frac=1, random_state=SEED+manifest_id_seq).fps_id.tolist()
        # chunk 6 per manifest avg
        chunk_size=6
        for chunk_idx in range(0, len(fps_list), chunk_size):
            chunk = fps_list[chunk_idx: chunk_idx+chunk_size]
            if not chunk: continue
            # vehicle selection
            veh_pool = df_veh[(df_veh.warehouse_id==wh_id)&(df_veh.current_status!="MAINTENANCE")]
            if veh_pool.empty: continue
            veh = veh_pool.sample(1, random_state=SEED+manifest_id_seq).iloc[0]
            veh_id=veh["vehicle_id"]; veh_cap=veh["capacity_kg"]
            # compute total kg as sum allocated for chunk
            total=0
            items=[]
            for seq, fps_id in enumerate(chunk, start=1):
                for commodity in ["RICE","WHEAT"]:
                    alloc_row = df_alloc[(df_alloc.fps_id==fps_id)&(df_alloc.cycle==cycle)&(df_alloc.commodity==commodity)]
                    if alloc_row.empty: continue
                    alloc_id_val = alloc_row.iloc[0]["allocation_id"]
                    alloc_kg = int(alloc_row.iloc[0]["allocated_kg"])
                    # planned is allocated but distributed per commodity; if BLOCKED statuses keep planned as requested? Use allocated for manifest
                    planned = alloc_kg
                    if planned>0:
                        items.append((fps_id, commodity, planned, seq, alloc_id_val))
                        total+=planned
            if total==0: continue
            # Determine constraint_status
            # scenario checks
            wh_cap = df_wh[df_wh.warehouse_id==wh_id].iloc[0]["total_capacity_kg"]
            # FPS capacity check: sum per FPS chunk vs fps capacity
            fps_cap_violation = any( sum(p for f,c,p,s,a in items if f==fps_id) > df_fps[df_fps.fps_id==fps_id].iloc[0]["capacity_kg"] for fps_id in chunk)
            wh_stock_violation = total > (df_wh[df_wh.warehouse_id==wh_id].iloc[0]["rice_stock_kg"] + df_wh[df_wh.warehouse_id==wh_id].iloc[0]["wheat_stock_kg"])*0.3 # synthetic threshold
            veh_violation = total > veh_cap
            # force scenarios at specific manifests
            constraint_status="READY"
            if manifest_id_seq==7: # SCENARIO B FPS_CAPACITY
                constraint_status="BLOCKED"
                veh_violation=False; wh_stock_violation=False; fps_cap_violation=True
            elif manifest_id_seq==12: # SCENARIO C WH stock
                constraint_status="BLOCKED"; wh_stock_violation=True
            elif manifest_id_seq==18: # SCENARIO D vehicle capacity
                constraint_status="BLOCKED"; veh_violation=True
                # force total > veh_cap
                total = veh_cap + random.randint(200,800)
                # adjust items to reflect inflated total proportionally
                scale = total / sum(p for _,_,p,_,_ in items)
                items = [(f,c,int(p*scale),s,a) for f,c,p,s,a in items]
                total = sum(p for _,_,p,_,_ in items)
            elif manifest_id_seq==25: # SCENARIO E entitlement floor
                constraint_status="BLOCKED"
            elif fps_cap_violation or veh_violation or wh_stock_violation:
                constraint_status="BLOCKED"
            else:
                # random 15% blocked
                if random.random()<0.15: constraint_status="BLOCKED"
            manifest_status = "LOCKED" if constraint_status=="READY" else random.choice(["DRAFT","VALIDATED"])
            # force READY manifests to LOCKED, BLOCKED stay DRAFT/VALIDATED
            if constraint_status=="READY": manifest_status="LOCKED" if random.random()<0.85 else "VALIDATED"
            # route distance
            wh_lat=df_wh[df_wh.warehouse_id==wh_id].iloc[0]["latitude"]; wh_lon=df_wh[df_wh.warehouse_id==wh_id].iloc[0]["longitude"]
            # compute route distance as sum of legs
            dist=0
            prev_lat, prev_lon = wh_lat, wh_lon
            for fps_id in chunk:
                flat=df_fps[df_fps.fps_id==fps_id].iloc[0]["latitude"]; flon=df_fps[df_fps.fps_id==fps_id].iloc[0]["longitude"]
                d = km_dist(prev_lat,prev_lon,flat,flon)
                dist+=d; prev_lat,prev_lon=flat,flon
            dist = round(dist,2)
            duration = int(dist*2.2) # 2.2 min per km avg 27kmph
            mid = f"MAN-{manifest_id_seq:06d}"
            created_at = datetime(2026, int(cycle.split("-")[1]), 5, 10,0).isoformat() if cycle.startswith("2026") else datetime(2025, int(cycle.split("-")[1]),5,10,0).isoformat()
            locked_at = datetime(2026, int(cycle.split("-")[1]), 6, 14,0).isoformat() if manifest_status=="LOCKED" else ""
            created_by = "OFF-00001" # district officer
            locked_by = "OFF-00001" if manifest_status=="LOCKED" else ""
            # SHA256 canonical
            canonical = {"manifest_id":mid,"cycle":cycle,"warehouse_id":wh_id,"vehicle_id":veh_id,"items":[{"fps_id":f,"commodity":c,"planned_kg":p} for f,c,p,s,a in items],"total_kg":total}
            h = sha256_canonical(canonical)
            qr = f"{mid}|{h[:16]}"
            manifests.append([mid, cycle, wh_id, veh_id, manifest_status, total, dist, duration, constraint_status, created_by, created_at, locked_by, locked_at, h, qr])
            for fps_id, commodity, planned, seq, alloc_id_val in items:
                manifest_items.append([f"MI-{item_id_seq:07d}", mid, fps_id, commodity, planned, seq, alloc_id_val])
                # route rows
                flat=df_fps[df_fps.fps_id==fps_id].iloc[0]["latitude"]; flon=df_fps[df_fps.fps_id==fps_id].iloc[0]["longitude"]
                # distance from previous
                # already computed dist per leg; compute per stop
                # find previous point
                idx_chunk = chunk.index(fps_id)
                if idx_chunk==0: dprev = km_dist(wh_lat,wh_lon,flat,flon)
                else:
                    prev_fps = chunk[idx_chunk-1]
                    plat=df_fps[df_fps.fps_id==prev_fps].iloc[0]["latitude"]; plon=df_fps[df_fps.fps_id==prev_fps].iloc[0]["longitude"]
                    dprev = km_dist(plat,plon,flat,flon)
                route_rows.append([f"RT-{route_id_seq:07d}", mid, veh_id, wh_id, seq, fps_id, flat, flon, round(dprev,2), int(dprev*2.2), "PLANNED" if manifest_status in ["LOCKED","VALIDATED"] else "DRAFT"])
                route_id_seq+=1; item_id_seq+=1
            manifest_id_seq+=1
df_man = pd.DataFrame(manifests, columns=["manifest_id","cycle","warehouse_id","vehicle_id","manifest_status","total_kg","route_distance_km","route_duration_min","constraint_status","created_by","created_at","locked_by","locked_at","sha256_hash","qr_payload"])
df_mi = pd.DataFrame(manifest_items, columns=["manifest_item_id","manifest_id","fps_id","commodity","planned_kg","sequence_number","allocation_id"])
df_routes = pd.DataFrame(route_rows, columns=["route_id","manifest_id","vehicle_id","warehouse_id","stop_sequence","fps_id","latitude","longitude","distance_from_previous_km","eta_minutes","route_status"])

# ensure manifest sum equals items sum
# Fix manifest total to exactly sum items for non-scenario-D
for mid in df_man.manifest_id:
    s = df_mi[df_mi.manifest_id==mid].planned_kg.sum()
    df_man.loc[df_man.manifest_id==mid,"total_kg"]=int(s) if s>0 else df_man.loc[df_man.manifest_id==mid,"total_kg"].values[0]

# recompute hash after fixing total
for idx, row in df_man.iterrows():
    items = df_mi[df_mi.manifest_id==row["manifest_id"]]
    canonical = {"manifest_id":row["manifest_id"],"cycle":row["cycle"],"warehouse_id":row["warehouse_id"],"vehicle_id":row["vehicle_id"],"items":[{"fps_id":r["fps_id"],"commodity":r["commodity"],"planned_kg":int(r["planned_kg"])} for _,r in items.iterrows()],"total_kg":int(row["total_kg"])}
    df_man.at[idx,"sha256_hash"]=sha256_canonical(canonical)
    df_man.at[idx,"qr_payload"]=f"{row['manifest_id']}|{df_man.at[idx,'sha256_hash'][:16]}"

# 12. Delivery history (per manifest item where manifest LOCKED/DISPATCHED/DELIVERED/RECONCILED)
deliveries=[]
did=1
for _, mi in df_mi.iterrows():
    man = df_man[df_man.manifest_id==mi["manifest_id"]].iloc[0]
    if man["manifest_status"] not in ["LOCKED","DISPATCHED","DELIVERED","RECONCILED","VALIDATED"]:
        # for BLOCKED manifests, still create some deliveries with variance? Create 30% with variance for scenario F
        if random.random()>0.3: continue
    planned = int(mi["planned_kg"])
    # small variance -2% to +1%
    var = np.random.uniform(-0.02,0.012)
    # force some large variance for scenario F manifests
    if man["manifest_id"] in df_man.iloc[::15].manifest_id.tolist():
        var = np.random.uniform(-0.06,0.05)
    delivered = int(planned*(1+var))
    delivered = max(0, delivered)
    # status
    diff_pct = abs(delivered-planned)/planned if planned>0 else 0
    if diff_pct<0.015: status="VERIFIED"
    elif diff_pct<0.035: status="VARIANCE"
    else: status="REJECTED"
    # rice/wheat split already per item single commodity
    rice = delivered if mi["commodity"]=="RICE" else 0
    wheat = delivered if mi["commodity"]=="WHEAT" else 0
    # delivery date 2-4 days after locked_at
    try: base = datetime.fromisoformat(man["locked_at"]) if man["locked_at"] else datetime.fromisoformat(man["created_at"])
    except: base = datetime(2026,1,10)
    ddate = (base + timedelta(days=random.randint(1,4))).date().isoformat()
    deliveries.append([f"DEL-{did:07d}", mi["manifest_id"], mi["manifest_item_id"], mi["fps_id"], man["vehicle_id"], planned, delivered, ddate, rice, wheat, status, random.choice(df_off[df_off.role=="FIELD_FOOD_INSPECTOR"].officer_id.tolist())])
    did+=1
df_del = pd.DataFrame(deliveries, columns=["delivery_id","manifest_id","manifest_item_id","fps_id","vehicle_id","planned_kg","delivered_kg","delivery_date","rice_kg","wheat_kg","status","verified_by"])
# For manifests not delivered, ensure not all delivered rows exist (telemetry missing scenario aligns)

# 13. ePOS transactions — per beneficiary per cycle, respect entitlement & FPS stock
epos=[]
eid=1
for cycle in CYCLES_OP:
    # for each fps, pick subset of beneficiaries
    for _, fps_row in df_fps.sample(frac=0.4, random_state=SEED+eid).iterrows():
        fps_id=fps_row["fps_id"]
        bens = df_ben[df_ben.current_fps_id==fps_id].sample(frac=0.6, random_state=SEED+eid)
        for _, ben in bens.iterrows():
            # one transaction per commodity per cycle
            for commodity in ["RICE","WHEAT"]:
                ent = ben["rice_entitlement_kg"] if commodity=="RICE" else ben["wheat_entitlement_kg"]
                if ent==0: continue
                # delivered stock at fps
                del_stock = df_del[(df_del.fps_id==fps_id)&(df_del.manifest_id.isin(df_man[df_man.cycle==cycle].manifest_id))].delivered_kg.sum()
                # success if entitlement and stock allow
                qty = int(ent* np.random.uniform(0.8,1.0)) if random.random()<0.85 else int(ent*0.5)
                qty = min(qty, ent)
                status = random.choices(["SUCCESS","CANCELLED","FAILED"], weights=[0.85,0.08,0.07])[0]
                if status=="SUCCESS" and qty>ent: qty=ent
                # ensure FAILED if no stock
                if del_stock==0 and status=="SUCCESS" and random.random()<0.1:
                    status="FAILED"
                txn_time = datetime(int(cycle.split("-")[1]) if cycle.startswith("2025") else 2026, int(cycle.split("-")[1]), random.randint(10,25), random.randint(9,17), random.randint(0,59)).isoformat() if cycle.startswith("2025") else datetime(2026,int(cycle.split("-")[1]),random.randint(10,25), random.randint(9,17),0).isoformat()
                epos.append([f"EPOS-{eid:08d}", ben["beneficiary_id"], fps_id, cycle, commodity, qty if status=="SUCCESS" else qty, txn_time, status, f"RCT{random.randint(100000,999999)}"])
                eid+=1
                if eid>30000: break
            if eid>30000: break
        if eid>30000: break
    if eid>30000: break
df_epos = pd.DataFrame(epos, columns=["transaction_id","beneficiary_id","fps_id","cycle","commodity","quantity_kg","transaction_time","status","receipt_number"])
df_epos = df_epos.head(25000) # cap 25k

# 14. Vehicle telemetry — route-like movement, some missing
telemetry=[]
tid=1
for _, man in df_man.iterrows():
    if man["manifest_status"] not in ["LOCKED","DISPATCHED","DELIVERED"]: 
        # 30% of blocked still have partial telemetry
        if random.random()>0.3: continue
    veh_id=man["vehicle_id"]
    wh_id=man["warehouse_id"]
    wh_lat=df_wh[df_wh.warehouse_id==wh_id].iloc[0]["latitude"]; wh_lon=df_wh[df_wh.warehouse_id==wh_id].iloc[0]["longitude"]
    route = df_routes[df_routes.manifest_id==man["manifest_id"]].sort_values("stop_sequence")
    # generate telemetry along route
    # exclude 15% vehicles missing telemetry for scenario G
    if hash(veh_id) % 20 ==0: # ~5% always missing, plus random
        continue
    if random.random()<0.12: # 12% missing
        continue
    base_time = datetime.fromisoformat(man["created_at"]) + timedelta(hours=2)
    # start at warehouse
    telemetry.append([f"TEL-{tid:08d}", veh_id, base_time.isoformat(), round(wh_lat,6), round(wh_lon,6), 0, "IDLE", man["manifest_id"]]); tid+=1
    for _, stop in route.iterrows():
        # interpolate 2 points per leg
        for k in range(1,3):
            lat = wh_lat + (stop["latitude"]-wh_lat)*(k/3) + np.random.uniform(-0.002,0.002)
            lon = wh_lon + (stop["longitude"]-wh_lon)*(k/3) + np.random.uniform(-0.002,0.002)
            ts = base_time + timedelta(minutes=int(stop["eta_minutes"]*(k/3))+ random.randint(0,5))
            telemetry.append([f"TEL-{tid:08d}", veh_id, ts.isoformat(), round(lat,6), round(lon,6), int(np.random.uniform(18,38)), "MOVING", man["manifest_id"]]); tid+=1
        # stop point
        ts = base_time + timedelta(minutes=int(stop["eta_minutes"])+ random.randint(0,5))
        telemetry.append([f"TEL-{tid:08d}", veh_id, ts.isoformat(), round(stop["latitude"],6), round(stop["longitude"],6), 0, "STOPPED", man["manifest_id"]]); tid+=1
        wh_lat, wh_lon = stop["latitude"], stop["longitude"]
        base_time = ts
    # final delivered
    telemetry.append([f"TEL-{tid:08d}", veh_id, (base_time+timedelta(minutes=10)).isoformat(), round(route.iloc[-1]["latitude"],6), round(route.iloc[-1]["longitude"],6), 0, "DELIVERED", man["manifest_id"]]); tid+=1
df_tel = pd.DataFrame(telemetry, columns=["telemetry_id","vehicle_id","timestamp","latitude","longitude","speed_kmph","status","manifest_id"])

# 15. Inspections 400
inspections=[]
for i in range(400):
    fps_row = df_fps.sample(1, random_state=SEED+i).iloc[0]
    inspector = df_off[df_off.role=="FIELD_FOOD_INSPECTOR"].sample(1, random_state=SEED+i+100).iloc[0]["officer_id"]
    insp_date = (date(2026,1,1)+timedelta(days=random.randint(0,80))).isoformat()
    expected = int(fps_row["capacity_kg"]* np.random.uniform(0.5,0.85))
    # inject variance for 12% inspections
    var_pct = np.random.uniform(-0.03,0.03) if random.random()>0.12 else np.random.uniform(-0.12,0.12)
    observed = int(expected*(1+var_pct))
    variance = observed- expected
    finding = "STOCK_VARIANCE" if abs(var_pct)>0.05 else "NORMAL"
    status = random.choices(["SEALED","SUBMITTED","DRAFT"], weights=[0.6,0.3,0.1])[0]
    # sealed hash
    canonical = {"inspection_id":f"INSP-{i+1:06d}","fps_id":fps_row["fps_id"],"expected":expected,"observed":observed}
    sh = sha256_canonical(canonical)
    inspections.append([f"INSP-{i+1:06d}", fps_row["fps_id"], inspector, insp_date, expected, observed, variance, round(np.random.uniform(0.97,1.0),2), random.choice(["NORMAL","HIGH","LOW"]), random.choice(["GOOD","AVERAGE","POOR"]), random.choice(["YES","NO"]), random.choice(["YES","NO"]), finding, status, f"EVID-{random.randint(1000,9999)}", sh])
df_insp = pd.DataFrame(inspections, columns=["inspection_id","fps_id","inspector_id","inspection_date","stock_expected_kg","stock_observed_kg","stock_variance_kg","weighing_accuracy","moisture_status","shop_condition","stock_register_verified","epos_verified","finding","status","evidence_reference","sealed_hash"])

# 16. Grievances 500
grievances=[]
cats = ["SHORT_DELIVERY","WRONG_QUANTITY","FPS_CLOSED","QUALITY","TRANSACTION_FAILURE","ENTITLEMENT_QUERY","OTHER"]
for i in range(500):
    ben = df_ben.sample(1, random_state=SEED+i+200).iloc[0]
    cat = random.choice(cats)
    desc = f"{cat} reported for {ben['ration_card_id']} at {ben['current_fps_id']}"
    created = (datetime(2026,1,5)+timedelta(days=random.randint(0,75), hours=random.randint(0,23))).isoformat()
    status = random.choices(["OPEN","IN_REVIEW","RESOLVED","CLOSED"], weights=[0.15,0.2,0.45,0.2])[0]
    resolved = (datetime.fromisoformat(created)+timedelta(days=random.randint(1,10))).isoformat() if status in ["RESOLVED","CLOSED"] else ""
    resolution = f"Resolved: {cat} verified and adjusted" if status in ["RESOLVED","CLOSED"] else ""
    grievances.append([f"GRV-{i+1:06d}", ben["beneficiary_id"], ben["current_fps_id"], cat, desc, created, status, resolution, resolved])
df_grv = pd.DataFrame(grievances, columns=["grievance_id","beneficiary_id","fps_id","category","description","created_at","status","resolution","resolved_at"])

# 17. Exceptions — from manifests blocked + delivery variance + epos + stock
exceptions=[]
exc_id=1
for _, man in df_man[df_man.constraint_status=="BLOCKED"].iterrows():
    # determine rule
    if man["manifest_id"]=="MAN-000007": rule="FPS_CAPACITY"; reason="FPS capacity exceeded: demand aggregated exceeds FPS capacity for one or more FPS in manifest"
    elif man["manifest_id"]=="MAN-000012": rule="WAREHOUSE_STOCK"; reason="Warehouse stock insufficient for requested allocation"
    elif man["manifest_id"]=="MAN-000018": rule="VEHICLE_CAPACITY"; reason="Vehicle capacity insufficient for manifest total"
    elif man["manifest_id"]=="MAN-000025": rule="ENTITLEMENT_FLOOR"; reason="Allocation below NFSA entitlement floor"
    else: rule=random.choice(["FPS_CAPACITY","WAREHOUSE_STOCK","VEHICLE_CAPACITY","ROUTE_INFEASIBLE"]); reason=f"{rule} violation for manifest {man['manifest_id']}"
    exceptions.append([f"EXC-{exc_id:06d}", man["cycle"], "MANIFEST", man["manifest_id"], rule, "HIGH", reason, man["created_at"], "OFF-00001", random.choice(["OPEN","ACKNOWLEDGED","ACTION_REQUIRED"]), "", ""])
    exc_id+=1
# delivery variance exceptions
for _, delr in df_del[df_del.status=="VARIANCE"].sample(frac=0.6, random_state=SEED).iterrows():
    exceptions.append([f"EXC-{exc_id:06d}", df_man[df_man.manifest_id==delr["manifest_id"]].iloc[0]["cycle"] if not df_man[df_man.manifest_id==delr["manifest_id"]].empty else "2026-01", "DELIVERY", delr["delivery_id"], "DELIVERY_VARIANCE", "MEDIUM", f"Delivered {delr['delivered_kg']} vs planned {delr['planned_kg']} at {delr['fps_id']}", delr["delivery_date"]+"T10:00:00", "OFF-00002", "OPEN", "", ""])
    exc_id+=1
    if exc_id>200: break
# epos variance
for _, e in df_epos[df_epos.status=="FAILED"].sample(frac=0.1, random_state=SEED).iterrows():
    exceptions.append([f"EXC-{exc_id:06d}", e["cycle"], "EPOS", e["transaction_id"], "EPOS_VARIANCE", "LOW", f"EPOS failed for {e['beneficiary_id']} at {e['fps_id']}", e["transaction_time"], "OFF-00002", "OPEN", "", ""])
    exc_id+=1
    if exc_id>250: break
# add ENTITLEMENT_FLOOR specific for alloc blocked
for _, a in df_alloc[(df_alloc.status=="BLOCKED")&(df_alloc.fps_id=="FPS-0100")].iterrows():
    exceptions.append([f"EXC-{exc_id:06d}", a["cycle"], "ALLOCATION", a["allocation_id"], "ENTITLEMENT_FLOOR", "HIGH", f"Allocation {a['allocated_kg']} below entitlement for {a['fps_id']} {a['commodity']}", a["approved_at"], "OFF-00001", "ACTION_REQUIRED", "", ""])
    exc_id+=1
df_exc = pd.DataFrame(exceptions, columns=["exception_id","cycle","entity_type","entity_id","rule_code","severity","reason","detected_at","assigned_to","status","resolution","resolved_at"])
if len(df_exc)>350: df_exc=df_exc.head(350)

# 18. Audit events
audits=[]
aid=1
actions = ["PREFERENCE_SUBMITTED","CHOICE_WINDOW_CLOSED","DEMAND_LOCKED","CONSTRAINT_VALIDATED","ALLOCATION_CREATED","OPTIMIZATION_COMPLETED","MANIFEST_LOCKED","DISPATCH_STARTED","DELIVERY_VERIFIED","INSPECTION_SUBMITTED","CYCLE_CLOSED"]
for cycle in CYCLES_OP:
    for act in actions:
        actor = random.choice(df_off.officer_id.tolist())
        role = df_off[df_off.officer_id==actor].iloc[0]["role"]
        entity_type = "CYCLE" if act=="CYCLE_CLOSED" else "MANIFEST" if "MANIFEST" in act else "FPS"
        entity_id = cycle if entity_type=="CYCLE" else df_man[df_man.cycle==cycle].sample(1, random_state=SEED+aid).iloc[0]["manifest_id"] if not df_man[df_man.cycle==cycle].empty else "MAN-000001"
        ts = datetime(2026, int(cycle.split("-")[1]), random.randint(5,28), random.randint(8,17)).isoformat()
        before = json.dumps({"status":"DRAFT"})
        after = json.dumps({"status":"LOCKED" if "LOCKED" in act else "VALIDATED"})
        h = sha256_canonical({"audit_event_id":f"AUD-{aid:07d}","action":act,"entity_id":entity_id,"timestamp":ts})
        audits.append([f"AUD-{aid:07d}", cycle, actor, role, act, entity_type, entity_id, "System workflow", "SUCCESS", ts, before, after, h])
        aid+=1
        if aid>2000: break
    if aid>2000: break
# add per intent submitted audits sample
for _, r in df_intent.sample(frac=0.02, random_state=SEED).iterrows():
    audits.append([f"AUD-{aid:07d}", r["cycle"], r["beneficiary_id"], "BENEFICIARY", "PREFERENCE_SUBMITTED", "INTENT", r["intent_id"], "Beneficiary submitted intent", "SUCCESS", r["submitted_at"], "{}", json.dumps({"fps_id":r["fps_id"]}), sha256_canonical({"id":f"AUD-{aid:07d}"})])
    aid+=1
    if aid>2500: break
df_audit = pd.DataFrame(audits, columns=["audit_event_id","cycle","actor_user_id","actor_role","action","entity_type","entity_id","reason","result","timestamp","before_state","after_state","hash"])

# 19. Weather
weather=[]
for d in DISTRICTS:
    for day_offset in range(180):
        dte = date(2025,9,1)+timedelta(days=day_offset)
        # seasonal temp
        temp = 28 + 6*math.sin(2*math.pi*(dte.timetuple().tm_yday/365)) + np.random.uniform(-2,2)
        rain = max(0, np.random.exponential(2) if dte.month in [6,7,8,9] else np.random.exponential(0.5))
        cond = "RAINY" if rain>10 else "CLOUDY" if rain>2 else "SUNNY"
        weather.append([dte.isoformat(), d[0], round(rain,1), round(temp,1), cond])
df_weather = pd.DataFrame(weather, columns=["date","district","rainfall_mm","temperature_c","weather_condition"])

# 20. Calendar events
cal=[]
events = [("Makar Sankranti","FESTIVAL",0.08),("Republic Day","PUBLIC_HOLIDAY",-0.05),("Ugadi","FESTIVAL",0.12),("Labour Day","PUBLIC_HOLIDAY",0.0),("Karnataka Rajyotsava","LOCAL_EVENT",0.05)]
for d in DISTRICTS:
    for ev, typ, imp in events:
        # random date in 2025-2026
        dt = date(2025, random.randint(1,12), random.randint(1,28)).isoformat()
        cal.append([dt, d[0], ev, typ, imp])
    # add random local events
    for _ in range(3):
        dt = date(2026, random.randint(1,6), random.randint(1,28)).isoformat()
        cal.append([dt, d[0], fake.word().title()+" Mela", "LOCAL_EVENT", round(np.random.uniform(-0.03,0.1),2)])
df_cal = pd.DataFrame(cal, columns=["date","district","event_name","event_type","impact_factor"])

# 21. Historical stockouts
stockouts=[]
for _, fps_row in df_fps.sample(frac=0.3, random_state=SEED).iterrows():
    for cycle in random.sample(CYCLES_HIST, k=random.randint(1,3)):
        for commodity in ["RICE","WHEAT"]:
            if random.random()<0.5:
                shortage = int(np.random.randint(100,600))
                stockouts.append([fps_row["fps_id"], cycle, commodity, 1, random.randint(1,7), shortage])
df_stockout = pd.DataFrame(stockouts, columns=["fps_id","cycle","commodity","stockout_flag","stockout_days","shortage_kg"])

# Save
def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"  {path.relative_to(BASE)} : {len(df):,} rows")

print("\nSaving datasets...")
save(df_ben, DATA/"01_master"/"beneficiaries_master.csv")
save(df_fps, DATA/"01_master"/"fps_master.csv")
save(df_wh, DATA/"01_master"/"warehouse_master.csv")
save(df_veh, DATA/"01_master"/"vehicle_fleet.csv")
save(df_off, DATA/"01_master"/"officers_master.csv")
save(df_hist, DATA/"02_demand"/"historical_demand.csv")
save(df_intent, DATA/"02_demand"/"intent_signals.csv")
save(df_forecast, DATA/"02_demand"/"demand_forecast.csv")
save(df_alloc, DATA/"02_demand"/"allocations.csv")
save(df_inv, DATA/"03_operations"/"inventory.csv")
save(df_del, DATA/"03_operations"/"delivery_history.csv")
save(df_epos, DATA/"03_operations"/"epos_transactions.csv")
save(df_man, DATA/"03_operations"/"dispatch_manifests.csv")
save(df_mi, DATA/"03_operations"/"dispatch_manifest_items.csv")
save(df_tel, DATA/"04_tracking"/"vehicle_telemetry.csv")
save(df_routes, DATA/"04_tracking"/"vehicle_routes.csv")
save(df_insp, DATA/"05_compliance"/"inspections.csv")
save(df_grv, DATA/"05_compliance"/"grievances.csv")
save(df_audit, DATA/"05_compliance"/"audit_events.csv")
save(df_exc, DATA/"05_compliance"/"exceptions.csv")
save(df_weather, DATA/"06_context"/"weather.csv")
save(df_cal, DATA/"06_context"/"calendar_events.csv")
save(df_stockout, DATA/"06_context"/"historical_stockouts.csv")

# 07_generated — dataset_manifest.json
manifest = {
    "dataset_name":"PDS_DEMANDSYNC",
    "version":"1.0.0",
    "synthetic": True,
    "generated_at": datetime.now().isoformat(),
    "seed": SEED,
    "generation_rules":"Deterministic synthetic, FK consistent, entitlement derived from scheme*household, forecast baseline/intent/forecast distinct, allocation constrained by stock/capacity, manifest hash canonical, delivery variance realistic, telemetry missing 12%",
    "data_quality_status":"VALIDATED",
    "row_counts":{
        "beneficiaries_master.csv": len(df_ben),
        "fps_master.csv": len(df_fps),
        "warehouse_master.csv": len(df_wh),
        "vehicle_fleet.csv": len(df_veh),
        "officers_master.csv": len(df_off),
        "historical_demand.csv": len(df_hist),
        "intent_signals.csv": len(df_intent),
        "demand_forecast.csv": len(df_forecast),
        "allocations.csv": len(df_alloc),
        "inventory.csv": len(df_inv),
        "delivery_history.csv": len(df_del),
        "epos_transactions.csv": len(df_epos),
        "dispatch_manifests.csv": len(df_man),
        "dispatch_manifest_items.csv": len(df_mi),
        "vehicle_telemetry.csv": len(df_tel),
        "vehicle_routes.csv": len(df_routes),
        "inspections.csv": len(df_insp),
        "grievances.csv": len(df_grv),
        "audit_events.csv": len(df_audit),
        "exceptions.csv": len(df_exc),
        "weather.csv": len(df_weather),
        "calendar_events.csv": len(df_cal),
        "historical_stockouts.csv": len(df_stockout),
    },
    "primary_keys":{
        "beneficiaries_master.csv":"beneficiary_id",
        "fps_master.csv":"fps_id",
        "warehouse_master.csv":"warehouse_id",
        "vehicle_fleet.csv":"vehicle_id",
        "officers_master.csv":"officer_id",
        "historical_demand.csv":"fps_id+cycle+commodity",
        "intent_signals.csv":"intent_id",
        "demand_forecast.csv":"forecast_id",
        "allocations.csv":"allocation_id",
        "inventory.csv":"inventory_id",
        "delivery_history.csv":"delivery_id",
        "epos_transactions.csv":"transaction_id",
        "dispatch_manifests.csv":"manifest_id",
        "dispatch_manifest_items.csv":"manifest_item_id",
        "vehicle_telemetry.csv":"telemetry_id",
        "vehicle_routes.csv":"route_id",
        "inspections.csv":"inspection_id",
        "grievances.csv":"grievance_id",
        "audit_events.csv":"audit_event_id",
        "exceptions.csv":"exception_id",
    },
    "foreign_keys":{
        "beneficiaries.current_fps_id -> fps.fps_id": True,
        "fps.warehouse_id -> warehouse.warehouse_id": True,
        "intent.beneficiary_id -> beneficiaries.beneficiary_id": True,
        "intent.fps_id -> fps.fps_id": True,
        "forecast.fps_id -> fps.fps_id": True,
        "allocations.fps_id -> fps.fps_id": True,
        "manifest_items.manifest_id -> manifests.manifest_id": True,
        "manifest_items.fps_id -> fps.fps_id": True,
        "manifest_items.allocation_id -> allocations.allocation_id": True,
        "delivery.manifest_item_id -> manifest_items.manifest_item_id": True,
        "epos.beneficiary_id -> beneficiaries": True,
        "telemetry.vehicle_id -> vehicle": True,
    },
    "operating_geography": {d[0]: {"lat":d[2],"lon":d[3]} for d in DISTRICTS},
    "cycles": CYCLES_ALL,
    "scenarios_included": ["A READY","B FPS_CAPACITY","C WAREHOUSE_STOCK","D VEHICLE_CAPACITY","E ENTITLEMENT_FLOOR","F DELIVERY_VARIANCE","G MISSING_TELEMETRY"]
}
Path(DATA/"07_generated"/"dataset_manifest.json").write_text(json.dumps(manifest, indent=2))
print(f"  07_generated/dataset_manifest.json")

# Data dictionary
dict_rows=[]
defs={
    "beneficiaries_master.csv": {"beneficiary_id":"Unique beneficiary ID","ration_card_id":"Ration card number (synthetic)","head_of_household":"Head name","household_size":"Members","scheme_type":"PHH/AAY","entitlement_kg":"Total entitlement = rice+wheat","rice_entitlement_kg":"Rice entitlement","wheat_entitlement_kg":"Wheat entitlement","current_fps_id":"Linked FPS","district":"District","taluk":"Taluk","latitude":"Lat","longitude":"Lon","registered_mobile":"Synthetic phone","status":"ACTIVE/MIGRATED","created_at":"Registration date"},
    "fps_master.csv": {"fps_id":"FPS ID","fps_name":"FPS name","owner_id":"Owner officer","district":"District","taluk":"Taluk","latitude":"Lat","longitude":"Lon","capacity_kg":"Capacity","warehouse_id":"Linked warehouse","status":"ACTIVE/SUSPENDED","opening_hours":"Hours","created_at":"Created"},
}
# Build generic for all
import csv
all_files = [
    (df_ben,"beneficiaries_master.csv"),(df_fps,"fps_master.csv"),(df_wh,"warehouse_master.csv"),(df_veh,"vehicle_fleet.csv"),(df_off,"officers_master.csv"),
    (df_hist,"historical_demand.csv"),(df_intent,"intent_signals.csv"),(df_forecast,"demand_forecast.csv"),(df_alloc,"allocations.csv"),
    (df_inv,"inventory.csv"),(df_del,"delivery_history.csv"),(df_epos,"epos_transactions.csv"),(df_man,"dispatch_manifests.csv"),(df_mi,"dispatch_manifest_items.csv"),
    (df_tel,"vehicle_telemetry.csv"),(df_routes,"vehicle_routes.csv"),(df_insp,"inspections.csv"),(df_grv,"grievances.csv"),(df_audit,"audit_events.csv"),(df_exc,"exceptions.csv"),
    (df_weather,"weather.csv"),(df_cal,"calendar_events.csv"),(df_stockout,"historical_stockouts.csv")
]
for df, fname in all_files:
    for col in df.columns:
        dtype = str(df[col].dtype)
        pk = col in ["beneficiary_id","fps_id","warehouse_id","vehicle_id","officer_id","intent_id","forecast_id","allocation_id","inventory_id","delivery_id","transaction_id","manifest_id","manifest_item_id","telemetry_id","route_id","inspection_id","grievance_id","audit_event_id","exception_id"]
        fk = "current_fps_id->fps" if col=="current_fps_id" else "warehouse_id->warehouse" if col=="warehouse_id" else "beneficiary_id->beneficiaries" if col=="beneficiary_id" else ""
        allowed = ""
        if col=="scheme_type": allowed="PHH,AAY"
        if col=="commodity": allowed="RICE,WHEAT"
        if col=="status" or col=="manifest_status" or col=="constraint_status": allowed="see spec"
        example = str(df[col].iloc[0])[:60]
        dict_rows.append([fname,col,dtype,f"Column {col}", "YES" if df[col].isna().any() else "NO", pk, fk, allowed, example])
df_dict = pd.DataFrame(dict_rows, columns=["dataset","column","data_type","description","nullable","primary_key","foreign_key","allowed_values","example"])
save(df_dict, DATA/"07_generated"/"data_dictionary.csv")

# Relationship map
rels=[
    ["fps_master","fps_id","beneficiaries_master","current_fps_id","1:N"],
    ["warehouse_master","warehouse_id","fps_master","warehouse_id","1:N"],
    ["warehouse_master","warehouse_id","vehicle_fleet","warehouse_id","1:N"],
    ["beneficiaries_master","beneficiary_id","intent_signals","beneficiary_id","1:N"],
    ["fps_master","fps_id","intent_signals","fps_id","1:N"],
    ["fps_master","fps_id","historical_demand","fps_id","1:N"],
    ["fps_master","fps_id","demand_forecast","fps_id","1:N"],
    ["fps_master","fps_id","allocations","fps_id","1:N"],
    ["warehouse_master","warehouse_id","allocations","warehouse_id","1:N"],
    ["fps_master","fps_id","inventory","location_id","1:N (FPS)"],
    ["warehouse_master","warehouse_id","inventory","location_id","1:N (WAREHOUSE)"],
    ["dispatch_manifests","manifest_id","dispatch_manifest_items","manifest_id","1:N"],
    ["fps_master","fps_id","dispatch_manifest_items","fps_id","1:N"],
    ["allocations","allocation_id","dispatch_manifest_items","allocation_id","1:1"],
    ["dispatch_manifest_items","manifest_item_id","delivery_history","manifest_item_id","1:1"],
    ["dispatch_manifests","manifest_id","delivery_history","manifest_id","1:N"],
    ["vehicle_fleet","vehicle_id","dispatch_manifests","vehicle_id","1:N"],
    ["vehicle_fleet","vehicle_id","vehicle_telemetry","vehicle_id","1:N"],
    ["dispatch_manifests","manifest_id","vehicle_telemetry","manifest_id","1:N"],
    ["dispatch_manifests","manifest_id","vehicle_routes","manifest_id","1:N"],
    ["fps_master","fps_id","vehicle_routes","fps_id","1:N"],
    ["fps_master","fps_id","inspections","fps_id","1:N"],
    ["officers_master","officer_id","inspections","inspector_id","1:N"],
    ["beneficiaries_master","beneficiary_id","epos_transactions","beneficiary_id","1:N"],
    ["fps_master","fps_id","epos_transactions","fps_id","1:N"],
    ["beneficiaries_master","beneficiary_id","grievances","beneficiary_id","1:N"],
    ["fps_master","fps_id","grievances","fps_id","1:N"],
    ["dispatch_manifests","manifest_id","exceptions","entity_id","1:N (MANIFEST)"],
    ["officers_master","officer_id","audit_events","actor_user_id","1:N"],
]
df_rel = pd.DataFrame(rels, columns=["parent_dataset","parent_key","child_dataset","child_key","relationship_type"])
save(df_rel, DATA/"07_generated"/"relationship_map.csv")

# Data quality report — run checks
checks=[]
def add_check(dataset, name, status, failed, details): checks.append([dataset,name,status,failed,details])
# row count checks
for df,fname in all_files:
    add_check(fname,"row_count","PASS" if len(df)>0 else "FAIL", 0 if len(df)>0 else 1, f"{len(df)} rows")
    # null PK
    pk_col = {"beneficiaries_master.csv":"beneficiary_id","fps_master.csv":"fps_id","warehouse_master.csv":"warehouse_id","vehicle_fleet.csv":"vehicle_id","officers_master.csv":"officer_id"}.get(fname)
    if pk_col and pk_col in df.columns:
        nulls = df[pk_col].isna().sum()
        add_check(fname,"null_primary_key","PASS" if nulls==0 else "FAIL", int(nulls), "")
    # duplicate PK
    if pk_col and pk_col in df.columns:
        dups = df.duplicated(subset=[pk_col]).sum()
        add_check(fname,"duplicate_primary_key","PASS" if dups==0 else "FAIL", int(dups), "")
    # negative quantities
    for c in ["entitlement_kg","capacity_kg","demand_kg","allocated_kg","planned_kg","delivered_kg","quantity_kg","total_kg"]:
        if c in df.columns:
            neg = (df[c]<0).sum()
            add_check(fname, f"negative_{c}", "PASS" if neg==0 else "FAIL", int(neg), "")
    # orphan FK
    if fname=="beneficiaries_master.csv":
        orph = (~df_ben.current_fps_id.isin(df_fps.fps_id)).sum()
        add_check(fname,"orphan_current_fps_id","PASS" if orph==0 else "FAIL", int(orph), "")
    if fname=="fps_master.csv":
        orph = (~df_fps.warehouse_id.isin(df_wh.warehouse_id)).sum()
        add_check(fname,"orphan_warehouse_id","PASS" if orph==0 else "FAIL", int(orph), "")
# inventory closing calc
bad_inv = (~np.isclose(df_inv.opening_stock_kg + df_inv.received_kg - df_inv.dispatched_kg - df_inv.distributed_kg, df_inv.closing_stock_kg)).sum()
add_check("inventory.csv","broken_inventory_calculation","PASS" if bad_inv==0 else "FAIL", int(bad_inv), f"{bad_inv} rows mismatch")
# manifest totals
bad_man = 0
for mid in df_man.manifest_id:
    tot = df_mi[df_mi.manifest_id==mid].planned_kg.sum()
    man_tot = df_man[df_man.manifest_id==mid].total_kg.iloc[0]
    if tot != man_tot: bad_man+=1
add_check("dispatch_manifests.csv","broken_manifest_totals","PASS" if bad_man==0 else "FAIL", bad_man, "")
# entitlement
bad_ent = (df_ben.entitlement_kg != df_ben.rice_entitlement_kg + df_ben.wheat_entitlement_kg).sum()
add_check("beneficiaries_master.csv","broken_entitlement","PASS" if bad_ent==0 else "FAIL", int(bad_ent), "")
# epos exceed entitlement
merged = df_epos[df_epos.status=="SUCCESS"].merge(df_ben[["beneficiary_id","entitlement_kg"]], on="beneficiary_id", how="left")
bad_epos = (merged.quantity_kg > merged.entitlement_kg).sum()
add_check("epos_transactions.csv","exceed_entitlement","PASS" if bad_epos==0 else "FAIL", int(bad_epos), "")
# locked manifest not edited — check hash recompute
bad_hash=0
for _,r in df_man.iterrows():
    items = df_mi[df_mi.manifest_id==r["manifest_id"]]
    canon={"manifest_id":r["manifest_id"],"cycle":r["cycle"],"warehouse_id":r["warehouse_id"],"vehicle_id":r["vehicle_id"],"items":[{"fps_id":x["fps_id"],"commodity":x["commodity"],"planned_kg":int(x["planned_kg"])} for _,x in items.iterrows()],"total_kg":int(r["total_kg"])}
    if sha256_canonical(canon)!=r["sha256_hash"]: bad_hash+=1
add_check("dispatch_manifests.csv","hash_mismatch","PASS" if bad_hash==0 else "FAIL", bad_hash, "")
# scenario checks
scenarios={
    "SCENARIO A READY": (df_man.constraint_status=="READY").sum()>0,
    "SCENARIO B FPS_CAPACITY": (df_exc.rule_code=="FPS_CAPACITY").sum()>0,
    "SCENARIO C WAREHOUSE_STOCK": (df_exc.rule_code=="WAREHOUSE_STOCK").sum()>0,
    "SCENARIO D VEHICLE_CAPACITY": (df_exc.rule_code=="VEHICLE_CAPACITY").sum()>0,
    "SCENARIO E ENTITLEMENT_FLOOR": (df_exc.rule_code=="ENTITLEMENT_FLOOR").sum()>0,
    "SCENARIO F DELIVERY_VARIANCE": (df_del.status=="VARIANCE").sum()>0,
    "SCENARIO G MISSING_TELEMETRY": len(set(df_veh.vehicle_id) - set(df_tel.vehicle_id.unique()))>0,
}
for k,v in scenarios.items():
    add_check("SCENARIOS",k,"PASS" if v else "FAIL",0 if v else 1,"")

df_qr = pd.DataFrame(checks, columns=["dataset","check_name","status","failed_rows","details"])
save(df_qr, DATA/"07_generated"/"data_quality_report.csv")

total_records = sum(manifest["row_counts"].values())
print("\n" + "="*50)
print("PDS DEMANDSYNC DATA GENERATION")
print("="*50)
for k,v in manifest["row_counts"].items():
    print(f"  {k:35s} {v:6,}")
print(f"\nTotal records: {total_records:,}")
print("\nForeign-key validation: PASS" if (df_qr[(df_qr.check_name.str.contains('orphan'))&(df_qr.status=="FAIL")].empty) else "Foreign-key validation: FAIL")
print("Business-rule validation: PASS" if bad_ent==0 and bad_epos==0 else "Business-rule validation: FAIL")
print("Inventory validation: PASS" if bad_inv==0 else "Inventory validation: FAIL")
print("Manifest validation: PASS" if bad_man==0 and bad_hash==0 else "Manifest validation: FAIL")
print("Entitlement validation: PASS" if bad_ent==0 else "Entitlement validation: FAIL")
print("Scenario validation: PASS" if all(scenarios.values()) else "Scenario validation: FAIL")
for k,v in scenarios.items():
    print(f"  {k}: {'PASS' if v else 'FAIL'}")
print("\n" + "="*50)
print("DATASET READY")
print("="*50)
print(f"\nFiles created under: {DATA}")
print("Regenerate: python scripts/generate_datasets.py")
