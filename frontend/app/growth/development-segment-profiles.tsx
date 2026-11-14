"use client";

import {useEffect,useState} from "react";
import {RefreshCw,Users,AlertTriangle,Info} from "lucide-react";
import {useState as useLocalState} from "react";
import {ResponsiveContainer,PieChart,Pie,Cell,Tooltip,Legend,BarChart,Bar,XAxis,YAxis,CartesianGrid} from "recharts";
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
function segmentLabel(segment:Segment){
  const m=segment.feature_medians;
  if((m.frequency_30d??1)===0&&(m.recency_days??0)>=30)return "No recent transactions";
  if((m.frequency_30d??Infinity)<=2&&(m.recency_days??0)>=7&&(m.monthly_spend_trend_30d_vs_90d??0)<=-0.5)return "Low and declining activity";
  return segment.segment_name;
}
function segmentSummary(segment:Segment){
  const m=segment.feature_medians;
  if(segmentLabel(segment)==="No recent transactions")return "Median transaction frequency over 30 days is zero, with the last observed transaction around 40 days ago.";
  if(segmentLabel(segment)==="Low and declining activity")return "Recent transaction frequency is low and the 30-day spend run rate is materially below the preceding 90-day monthly run rate.";
  return segment.summary;
}

export default function DevelopmentSegmentProfiles(){
  const [profile,setProfile]=useState<Profile|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  const [selectedFeature,setSelectedFeature]=useLocalState("recency_days");
  const palette=["#2563eb","#0d9488","#d97706","#7c3aed","#db2777"];
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
        <article className="panel" style={{boxShadow:"none"}}>
          <div className="panel-heading"><div><h3 className="panel-title">Customer segment mix</h3><p className="panel-caption">Share of the profiled mock portfolio</p></div></div>
          <div style={{width:"100%",height:260}}><ResponsiveContainer><PieChart>
            <Pie data={profile.clusters.map(segment=>({...segment,segment_name:segmentLabel(segment)}))} dataKey="customer_count" nameKey="segment_name" cx="50%" cy="48%" innerRadius={62} outerRadius={94} paddingAngle={3}>
              {profile.clusters.map((segment,index)=><Cell key={segment.cluster_id} fill={palette[index%palette.length]}/>)}
            </Pie>
            <Tooltip formatter={(value)=>[number(Number(value)),"Customers"]}/><Legend verticalAlign="bottom" height={34}/>
          </PieChart></ResponsiveContainer></div>
        </article>
        <article className="panel" style={{boxShadow:"none"}}>
          <div className="panel-heading"><div><h3 className="panel-title">Behavioural feature comparison</h3><p className="panel-caption">Median value by segment; compare one measure at a time</p></div></div>
          <label className="small-note" htmlFor="segment-feature-select">Feature</label>
          <select id="segment-feature-select" className="form-input" value={selectedFeature} onChange={event=>setSelectedFeature(event.target.value)} style={{maxWidth:320,margin:"6px 0 10px"}}>
            {Array.from(new Set(profile.clusters.flatMap(segment=>Object.keys(segment.feature_medians)))).map(key=><option key={key} value={key}>{labels[key]||key}</option>)}
          </select>
          <div style={{width:"100%",height:220}}><ResponsiveContainer><BarChart data={profile.clusters.map(segment=>({name:segmentLabel(segment),value:segment.feature_medians[selectedFeature]??0}))} margin={{top:8,right:12,left:0,bottom:8}}>
            <CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="name" tick={{fontSize:11}} interval={0}/><YAxis tick={{fontSize:11}}/>
            <Tooltip formatter={(value)=>[number(Number(value)),labels[selectedFeature]||selectedFeature]}/>
            <Bar dataKey="value" name={labels[selectedFeature]||selectedFeature} fill="#2563eb" radius={[5,5,0,0]}/>
          </BarChart></ResponsiveContainer></div>
        </article>
      </div>
      <div className="dashboard-grid" style={{marginTop:14}}>
        {profile.clusters.map(segment=><article className="panel" key={segment.cluster_id} style={{boxShadow:"none"}}>
          <div className="panel-heading"><div><span className="eyebrow">CLUSTER {segment.cluster_id}</span><h3 className="panel-title">{segmentLabel(segment)}</h3></div>
            {segment.small_cluster_review&&<span className="status-badge"><AlertTriangle size={13}/>Small cluster review</span>}
          </div>
          <div className="kpi-value">{number(segment.customer_count)}</div><div className="kpi-note">{number(segment.share_pct)}% of profiled customers</div>
          <div className="risk-driver-track" style={{margin:"12px 0 14px"}}><span style={{width:segment.share_pct+"%"}}/></div>
          <p className="panel-caption">{segmentSummary(segment)}</p>
          {segment.signals.length>0&&<div style={{marginTop:12}}><strong className="small-note">Relative signals</strong><ul className="segment-signal-list">{segment.signals.map(signal=><li key={signal}>{signal}</li>)}</ul></div>}
          <div className="table-scroll" style={{marginTop:12}}><table className="table"><thead><tr><th>Feature median</th><th>Value</th></tr></thead><tbody>{Object.entries(segment.feature_medians).map(([key,value])=><tr key={key}><td>{labels[key]||key}</td><td>{number(value)}</td></tr>)}</tbody></table></div>
        </article>)}
      </div>
      <p className="governance-note">{profile.interpretation_note} The smallest clusters are flagged for manual statistical review; no customer identities or individual assignments are displayed.</p>
      <DevelopmentSegmentationComparison enabled={!!profile && !loading} />
    </>}
  </section>;
}
