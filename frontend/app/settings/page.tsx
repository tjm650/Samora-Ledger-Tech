"use client";
import {useEffect,useState} from "react";
import {SlidersHorizontal,PanelLeft,ShieldCheck} from "lucide-react";

export default function SettingsPage(){
 const [periodDays,setPeriodDays]=useState("90");
 const [message,setMessage]=useState("");
 const [loading,setLoading]=useState(true);
 useEffect(()=>{
  let active=true;
  void fetch("/api/settings/preferences",{cache:"no-store"})
   .then(async r=>{const b=await r.json();if(!r.ok)throw new Error(b.error||"Unable to retrieve workspace preferences");return b})
   .then(b=>{if(!active)return;const saved=(b.preferences||[]).find((x:any)=>x.preference_key==="default_reporting_period");if(saved?.preference_value?.value)setPeriodDays(String(saved.preference_value.value))})
   .catch(e=>{if(active)setMessage(e instanceof Error?e.message:"Unable to retrieve workspace preferences.")})
   .finally(()=>{if(active)setLoading(false)});
  return()=>{active=false};
 },[]);
 async function save(){
  setMessage("");
  try{
   const r=await fetch("/api/settings/preferences",{method:"PATCH",headers:{"Content-Type":"application/json"},body:JSON.stringify({preference_key:"default_reporting_period",preference_value:{value:periodDays}})});
   const b=await r.json();if(!r.ok)throw new Error(b.error||"Unable to save preference");
   setMessage("Your reporting preference has been saved.");
  }catch(e){setMessage(e instanceof Error?e.message:"Unable to save preference")}
 }
 return <>
  <div className="governance-grid">
   <section className="panel"><SlidersHorizontal size={20} color="#147d78"/><h2 className="panel-title" style={{marginTop:12}}>Navigation layout</h2><p className="panel-caption">Navigate the workspace using the persistent sidebar.</p><ul className="business-list"><li>Use the collapse control to switch to compact icon navigation.</li><li>On mobile, open the navigation using the menu control in the header.</li><li>Choose Overview, CRM, Transactions, Risk, Analytics, Reports or Model Governance from the sidebar.</li><li>Customer profiles open directly from the CRM directory.</li></ul></section>
   <section className="panel"><PanelLeft size={20} color="#147d78"/><h2 className="panel-title" style={{marginTop:12}}>Workspace preferences</h2><p className="panel-caption">Set the default reporting period used by supported analytics views.</p>{loading?<div className="empty-state">Loading workspace preferences…</div>:<><label className="block text-sm font-medium text-slate-700">Default analytics reporting period<select className="filter-select" style={{display:"block",marginTop:8}} value={periodDays} onChange={e=>setPeriodDays(e.target.value)}><option value="30">Last 30 days</option><option value="90">Last 90 days</option><option value="180">Last 180 days</option></select></label><button className="btn" style={{marginTop:16}} onClick={()=>void save()}>Save preference</button></>}{message&&<p className="governance-footnote" role="status">{message}</p>}</section>
  </div>
  <div className="governance-grid" style={{marginTop:18}}><section className="panel"><ShieldCheck size={20} color="#147d78"/><h2 className="panel-title" style={{marginTop:12}}>Demo workspace access</h2><p className="panel-caption">The sign-in interface has been removed from the website. Data API access remains governed by the backend while the public demo access model is finalised.</p><p className="governance-footnote">Do not place real customer or confidential banking information in this demonstration environment.</p></section></div>
 </>;
}
