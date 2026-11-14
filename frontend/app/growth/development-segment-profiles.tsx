"use client";

import {useEffect,useState} from "react";
import {RefreshCw,Users,AlertTriangle,Info} from "lucide-react";
import DevelopmentSegmentationComparison from "./development-segmentation-comparison";

type Segment={
  cluster_id:number;segment_name:string;customer_count:number;share_pct:number;
  summary:string;signals:string[];small_cluster_review:boolean;
  feature_medians:Record<string,number>;
};
type Profile={
  status:string;customers_profiled:number;silhouette_score:number|null;
  production_eligible:boolean;data_origin:string;clusters:Segment[];
  interpretation_note:string;
};
const labels:Record<string,string>={
  recency_days:"Days since last transaction",frequency_30d:"Transactions · 30 days",
  frequency_90d:"Transactions · 90 days",monetary_spend_90d:"Debit spend · 90 days",
  credit_inflow_90d:"Credit inflow · 90 days",active_days_90d:"Active days · 90 days",
  balance_avg_30d:"Average balance · 30 days"
};
const number=(v:number)=>new Intl.NumberFormat("en-US",{maximumFractionDigits:1}).format(v);
export default function DevelopmentSegmentProfiles(){
  const [profile,setProfile]=useState<Profile|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  async function load(){
    setLoading(true);setError("");
    try{
      const response=await fetch("/api/model-training/development-segmentation/profile",{cache:"no-store"});
      const body=await response.json();
      if(!response.ok)throw new Error(body.error||"Unable to load segment profiles.");
      setProfile(body);
    }catch(e){setError(e instanceof Error?e.message:"Unable to load segment profiles.");}
    finally{setLoading(false);}
  }
  useEffect(()=>{void load();},[]);
  return <section className="panel" style={{marginTop:18}}>
    <div className="panel-heading">
      <div><h2 className="panel-title">Customer behaviour segments</h2><p className="panel-caption">Aggregate profiles from the latest experimental K-means model</p></div>
      <button className="btn" onClick={()=>void load()} disabled={loading}><RefreshCw size={14}/>{loading?"Loading…":"Refresh profiles"}</button>
    </div>
    <div className="governance-callout" role="note"><Info size={15}/> Development experiment · Mock data only · Not a churn model · Not approved for production or customer-level decisions.</div>
    {error&&<div className="governance-callout" role="alert">{error}</div>}
    {loading&&!profile?<div className="empty-state">Loading aggregate segment profiles…</div>:null}
    {profile&&<>
      <div className="kpi-grid" style={{marginTop:14}}>
        <div className="kpi-card"><div className="kpi-label"><Users size={14}/>Customers profiled</div><div className="kpi-value">{number(profile.customers_profiled)}</div><div className="kpi-note">Quality-passed mock feature rows</div></div>
        <div className="kpi-card"><div className="kpi-label">Clusters</div><div className="kpi-value">{profile.clusters.length}</div><div className="kpi-note">Unsupervised K-means groups</div></div>
        <div className="kpi-card"><div className="kpi-label">Silhouette diagnostic</div><div className="kpi-value">{profile.silhouette_score==null?"—":number(profile.silhouette_score)}</div><div className="kpi-note">Cluster separation diagnostic, not accuracy</div></div>
      </div>
      <div className="dashboard-grid" style={{marginTop:14}}>
        {profile.clusters.map(segment=><article className="panel" key={segment.cluster_id} style={{boxShadow:"none"}}>
          <div className="panel-heading"><div><span className="eyebrow">CLUSTER {segment.cluster_id}</span><h3 className="panel-title">{segment.segment_name}</h3></div>
            {segment.small_cluster_review&&<span className="status-badge"><AlertTriangle size={13}/>Small cluster review</span>}
          </div>
          <div className="kpi-value">{number(segment.customer_count)}</div><div className="kpi-note">{number(segment.share_pct)}% of profiled customers</div>
          <div className="risk-driver-track" style={{margin:"12px 0 14px"}}><span style={{width:segment.share_pct+"%"}}/></div>
          <p className="panel-caption">{segment.summary}</p>
          {segment.signals.length>0&&<div style={{marginTop:12}}><strong className="small-note">Relative signals</strong><ul className="segment-signal-list">{segment.signals.map(signal=><li key={signal}>{signal}</li>)}</ul></div>}
          <div className="table-scroll" style={{marginTop:12}}><table className="table"><thead><tr><th>Feature median</th><th>Value</th></tr></thead><tbody>{Object.entries(segment.feature_medians).map(([key,value])=><tr key={key}><td>{labels[key]||key}</td><td>{number(value)}</td></tr>)}</tbody></table></div>
        </article>)}
      </div>
      <p className="governance-note">{profile.interpretation_note} The smallest clusters are flagged for manual statistical review; no customer identities or individual assignments are displayed.</p>
      <DevelopmentSegmentationComparison />
    </>}
  </section>;
}
