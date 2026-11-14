"use client";

import {useEffect,useState} from "react";
import {RefreshCw,Info} from "lucide-react";

type Comparison={from_snapshot:string;to_snapshot:string;overlapping_customers:number;status:string;adjusted_rand_index:number|null;from_cluster_shares_pct?:Record<string,number>;to_cluster_shares_pct?:Record<string,number>};
type Result={status:string;model_version_id:string;data_origin:string;snapshots_available:number;snapshot_sizes?:Array<{snapshot_at:string;customers_profiled:number}>;temporal_comparisons:Comparison[];mean_temporal_ari:number|null;interpretation_note:string};
export default function DevelopmentSegmentationTemporalStability(){
  const [data,setData]=useState<Result|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState("");
  async function load(){setLoading(true);setError("");try{const response=await fetch("/api/model-training/development-segmentation/temporal-stability",{cache:"no-store"});const body=await response.json();if(!response.ok)throw new Error(body.error||"Unable to review temporal stability.");setData(body);}catch(e){setError(e instanceof Error?e.message:"Unable to review temporal stability.");}finally{setLoading(false);}}
  useEffect(()=>{void load();},[]);
  return <section className="panel" style={{marginTop:18,boxShadow:"none"}}>
    <div className="panel-heading"><div><h3 className="panel-title">Temporal segment stability</h3><p className="panel-caption">Applies the same frozen model to historical mock feature snapshots</p></div><button className="btn" onClick={()=>void load()} disabled={loading}><RefreshCw size={14}/>{loading?"Reviewing…":"Refresh review"}</button></div>
    <div className="governance-callout" role="note"><Info size={15}/> Read-only review. It compares assignments only for customers present in adjacent snapshots. It does not rebuild features, create snapshots, or modify model records.</div>
    {error&&<div className="governance-callout" role="alert">{error}</div>}
    {loading&&!data&&<div className="empty-state">Reviewing historical snapshots…</div>}
    {data&&<>{data.status==="insufficient_historical_snapshots"?<div className="empty-state">Only {data.snapshots_available} eligible historical snapshot(s) are available. At least two distinct snapshots are required. This review will become evaluable after another legitimate feature-engineering run creates a new history snapshot.</div>:<>
      <div className="kpi-grid" style={{marginTop:14}}><div className="kpi-card"><div className="kpi-label">Snapshots reviewed</div><div className="kpi-value">{data.snapshots_available}</div></div><div className="kpi-card"><div className="kpi-label">Temporal comparisons</div><div className="kpi-value">{data.temporal_comparisons.filter(x=>x.status==="evaluated").length}</div></div><div className="kpi-card"><div className="kpi-label">Mean temporal ARI</div><div className="kpi-value">{data.mean_temporal_ari==null?"—":data.mean_temporal_ari.toFixed(3)}</div></div></div>
      <div className="table-scroll" style={{marginTop:12}}><table className="table"><thead><tr><th>From snapshot</th><th>To snapshot</th><th>Overlapping customers</th><th>ARI</th><th>Status</th></tr></thead><tbody>{data.temporal_comparisons.map((item,i)=><tr key={i}><td>{new Date(item.from_snapshot).toLocaleString()}</td><td>{new Date(item.to_snapshot).toLocaleString()}</td><td>{item.overlapping_customers}</td><td>{item.adjusted_rand_index==null?"—":item.adjusted_rand_index.toFixed(3)}</td><td>{item.status==="evaluated"?"Evaluated":"Insufficient overlap"}</td></tr>)}</tbody></table></div>
      {data.snapshot_sizes&&<p className="governance-note">{data.snapshot_sizes.map(x=>`${new Date(x.snapshot_at).toLocaleDateString()}: ${x.customers_profiled} customers`).join(" · ")}</p>}
    </>}
    <p className="governance-note">{data.interpretation_note} Model remains development-only, mock-only, experimental and inactive.</p></>}
  </section>;
}
