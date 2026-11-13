"use client";
import {useEffect,useState} from "react";
import HeaderActions from "@/app/components/header-actions";
import {Activity,BarChart3} from "lucide-react";
import {Bar,BarChart,CartesianGrid,Line,LineChart,ResponsiveContainer,Tooltip,XAxis,YAxis} from "recharts";
import {amount,number} from "@/lib/executive";
type Analytics={period_start:string;period_end:string;aggregation_interval:string;dimension:string;metrics:any;risk_metrics:any;transaction_trend:any[];category_breakdown:any[];channel_breakdown:any[];dimension_breakdown:any[]};
export default function AnalyticsPage(){
 const [data,setData]=useState<Analytics|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState("");
 const [start,setStart]=useState(()=>new Date(Date.now()-89*86400000).toISOString().slice(0,10));
 const [end,setEnd]=useState(()=>new Date().toISOString().slice(0,10));
 const [interval,setInterval]=useState("day");const [dimension,setDimension]=useState("category");const [saving,setSaving]=useState(false);
 async function load(save=false,startOverride=start){
  setLoading(true);setError("");
  try{
   const q=new URLSearchParams({start_date:startOverride,end_date:end,interval,dimension});if(save)q.set("save_snapshot","true");
   const r=await fetch(`/api/analytics/overview?${q.toString()}`,{cache:"no-store"});const b=await r.json();
   if(!r.ok)throw new Error(b.error||"Unable to load analytics");setData(b);
   if(save)setSaving(false);
  }catch(e){setError(e instanceof Error?e.message:"Unable to load analytics")}
  finally{setLoading(false);setSaving(false)}
 }
 useEffect(()=>{
  let active=true;
  void fetch("/api/settings/preferences",{cache:"no-store"}).then(r=>r.json()).then(b=>{
   if(!active)return;
   const saved=(b.preferences||[]).find((x:any)=>x.preference_key==="default_reporting_period");
   const days=Number(saved?.preference_value?.value);
   if(days===30||days===90||days===180){const nextStart=new Date(Date.now()-(days-1)*86400000).toISOString().slice(0,10);setStart(nextStart);void load(false,nextStart)}
   else void load();
  }).catch(()=>{if(active)void load()});
  return()=>{active=false};
 },[]);
 async function saveSnapshot(){setSaving(true);await load(true)}
 const m=data?.metrics,risk=data?.risk_metrics;
 const average=m?.transaction_count?((Number(m.debit_volume||0)+Number(m.credit_volume||0))/Number(m.transaction_count)):0;
 return <>
  <HeaderActions><span className="badge neutral"><BarChart3 size={12}/>Selected-period analysis</span></HeaderActions>
  {error&&<div className="alert" role="alert">{error}</div>}
  <div className="kpi-grid">
   <div className="kpi-card"><div className="kpi-label">Transaction volume</div><div className="kpi-value">{loading?"—":number(m?.transaction_count||0)}</div><div className="kpi-note">Debit and credit entries · selected period</div></div>
   <div className="kpi-card"><div className="kpi-label">Average transaction</div><div className="kpi-value">{loading?"—":amount(average)}</div><div className="kpi-note">Source currency · selected period</div></div>
   <div className="kpi-card"><div className="kpi-label">Net transaction flow</div><div className="kpi-value">{loading?"—":amount(m?.net_flow||0)}</div><div className="kpi-note">Credits less debits</div></div>
   <div className="kpi-card"><div className="kpi-label">Average risk score</div><div className="kpi-value">{loading?"—":Number(risk?.average_score||0).toFixed(1)}</div><div className="kpi-note">Current rules-based cohort</div></div>
  </div>
  <section className="panel"><div className="panel-heading"><div><h2 className="panel-title">Daily transaction value</h2><p className="panel-caption">Debit and credit movement · {data?.period_start||start} to {data?.period_end||end}</p></div><span className="panel-period">{(interval||"day").toUpperCase()}LY</span></div>
   <div className="chart-wrap chart-extra-tall">{loading?<div className="empty-state">Loading trend data…</div>:<ResponsiveContainer width="100%" height="100%"><LineChart data={data?.transaction_trend||[]} margin={{top:12,right:14,left:5,bottom:0}}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf1f4"/><XAxis dataKey="bucket" tickFormatter={v=>new Date(v).toLocaleDateString()} minTickGap={22} axisLine={false} tickLine={false} tick={{fontSize:10,fill:"#8290a0"}}/><YAxis axisLine={false} tickLine={false} tick={{fontSize:10,fill:"#8290a0"}}/><Tooltip labelFormatter={v=>new Date(String(v)).toLocaleString()} formatter={v=>amount(Number(v))}/><Line type="monotone" dataKey="debit_volume" name="Debits" stroke="#177d77" strokeWidth={2.4} dot={false}/><Line type="monotone" dataKey="credit_volume" name="Credits" stroke="#537e9e" strokeWidth={2.4} dot={false}/></LineChart></ResponsiveContainer>}</div>
   <div className="chart-legend"><span><i className="legend-dot teal"/>Debits</span><span><i className="legend-dot blue"/>Credits</span></div>
  </section>
  <div className="dashboard-grid lower-grid" style={{marginTop:18}}>
   <section className="panel"><div className="panel-heading"><div><h2 className="panel-title">Merchant category analysis</h2><p className="panel-caption">Value and activity by transaction category</p></div></div><div className="chart-wrap chart-tall">{loading?<div className="empty-state">Loading category analysis…</div>:<ResponsiveContainer width="100%" height="100%"><BarChart data={data?.category_breakdown||[]} margin={{top:8,right:12,left:0,bottom:0}}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#edf1f4"/><XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fontSize:9,fill:"#718096"}} interval={0}/><YAxis axisLine={false} tickLine={false} tick={{fontSize:10,fill:"#8290a0"}}/><Tooltip formatter={v=>amount(Number(v))}/><Bar dataKey="volume" name="Transaction value" fill="#177d77" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>}</div></section>
   <section className="panel"><div className="panel-heading"><div><h2 className="panel-title">Channel utilisation</h2><p className="panel-caption">Transaction count by recorded channel</p></div></div><div className="chart-wrap chart-tall">{loading?<div className="empty-state">Loading channel analysis…</div>:<ResponsiveContainer width="100%" height="100%"><BarChart data={data?.channel_breakdown||[]} layout="vertical" margin={{left:15,right:15,top:8,bottom:0}}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#edf1f4"/><XAxis type="number" allowDecimals={false} axisLine={false} tickLine={false} tick={{fontSize:10,fill:"#8290a0"}}/><YAxis type="category" dataKey="name" width={82} axisLine={false} tickLine={false} tick={{fontSize:10,fill:"#718096"}}/><Tooltip/><Bar dataKey="transaction_count" name="Transactions" fill="#537e9e" radius={[0,4,4,0]} maxBarSize={24}/></BarChart></ResponsiveContainer>}</div></section>
  </div>
  <details className="panel" style={{marginTop:18}}>
   <summary className="panel-heading" style={{cursor:"pointer"}}><div><h2 className="panel-title">Advanced reporting controls</h2><p className="panel-caption">Customise reporting dates, aggregation, analytical dimensions and saved snapshots</p></div><span className="panel-period">OPTIONAL</span></summary>
   <div className="table-toolbar" style={{paddingTop:14}}><label className="search-field"><span>Start date</span><input type="date" value={start} onChange={e=>setStart(e.target.value)}/></label><label className="search-field"><span>End date</span><input type="date" value={end} onChange={e=>setEnd(e.target.value)}/></label><select className="filter-select" value={interval} onChange={e=>setInterval(e.target.value)}><option value="day">Daily</option><option value="week">Weekly</option><option value="month">Monthly</option></select><select className="filter-select" value={dimension} onChange={e=>setDimension(e.target.value)}><option value="none">All transactions</option><option value="category">Category</option><option value="channel">Channel</option><option value="account_tier">Account tier</option><option value="behavior_segment">Behaviour segment</option></select><button className="btn" onClick={()=>void load()} disabled={loading||!start||!end||start>end}>Apply</button><button className="btn btn-secondary" onClick={()=>void saveSnapshot()} disabled={loading||saving}>{saving?"Saving…":"Save snapshot"}</button></div>
   <div className="kpi-grid" style={{marginTop:14}}><div className="kpi-card"><div className="kpi-label">Count change vs prior period</div><div className="kpi-value">{m?.transaction_count_change_pct===null||m?.transaction_count_change_pct===undefined?"—":Number(m.transaction_count_change_pct).toFixed(1)+"%"}</div><div className="kpi-note">Equal-length preceding period</div></div><div className="kpi-card"><div className="kpi-label">Debit value change</div><div className="kpi-value">{m?.debit_volume_change_pct===null||m?.debit_volume_change_pct===undefined?"—":Number(m.debit_volume_change_pct).toFixed(1)+"%"}</div><div className="kpi-note">Versus preceding period</div></div><div className="kpi-card"><div className="kpi-label">Credit value change</div><div className="kpi-value">{m?.credit_volume_change_pct===null||m?.credit_volume_change_pct===undefined?"—":Number(m.credit_volume_change_pct).toFixed(1)+"%"}</div><div className="kpi-note">Versus preceding period</div></div><div className="kpi-card"><div className="kpi-label">Selected dimension</div><div className="kpi-value" style={{fontSize:17}}>{dimension.replaceAll("_"," ")}</div><div className="kpi-note">{data?.dimension_breakdown?.length||0} grouped records</div></div></div>
   <section className="panel" style={{marginTop:14}}><div className="panel-heading"><div><h2 className="panel-title">Selected dimension breakdown</h2><p className="panel-caption">Value by {dimension.replaceAll("_"," ")}</p></div></div><div className="chart-wrap chart-tall">{loading?<div className="empty-state">Loading dimension analysis…</div>:<ResponsiveContainer width="100%" height="100%"><BarChart data={data?.dimension_breakdown||[]} layout="vertical" margin={{left:15,right:15,top:8,bottom:0}}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#edf1f4"/><XAxis type="number" axisLine={false} tickLine={false}/><YAxis type="category" dataKey="name" width={110} axisLine={false} tickLine={false} tick={{fontSize:10}}/><Tooltip formatter={v=>amount(Number(v))}/><Bar dataKey="volume" name="Transaction value" fill="#537e9e" radius={[0,4,4,0]} maxBarSize={24}/></BarChart></ResponsiveContainer>}</div></section>
  </details>
  <div className="governance-callout" style={{marginTop:18}}><Activity size={16}/><p>Analysis uses posted transaction records and the latest available scoring run. Monetary totals are not converted across currencies, and the current data model does not include branch, geography, product balance-sheet, fee or margin dimensions.</p></div>
 </>;
}
