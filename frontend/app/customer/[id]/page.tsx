"use client";
import {useEffect,useState} from "react";
import {useParams} from "next/navigation";
import Link from "next/link";
import {ArrowLeft,ShieldCheck,UserRound,Activity,Wallet,CalendarClock} from "lucide-react";

type Profile={customer?:{customer_id:string;full_name:string;email:string;account_tier:string;created_at:string};features?:{frequency_30d:number;balance_avg_30d:number;recency_days:number;salary_disruption_flag:boolean;velocity_score:number;balance_drawdown_pct:number;behavior_segment?:string}|null;insight?:{churn_risk_score:number;primary_churn_driver:string;recommended_product:string;prescriptive_action:string;evaluated_at:string}|null;explanation_type?:string};
export default function CustomerDetail(){
 const params=useParams<{id:string}>();const [data,setData]=useState<Profile|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 useEffect(()=>{async function load(){try{const response=await fetch("/api/customer/"+encodeURIComponent(params.id),{cache:"no-store"});const body=await response.json();if(!response.ok)throw new Error(body.error||"Unable to load customer profile");setData(body)}catch(e){setError(e instanceof Error?e.message:"Unable to load customer profile")}finally{setLoading(false)}}if(params.id)void load()},[params.id]);
 if(loading)return <div className="panel empty-state">Loading customer profile…</div>;
 if(error)return <div><Link href="/crm" className="link-action"><ArrowLeft size={13} style={{display:"inline"}}/> Back to portfolio</Link><div className="alert" style={{marginTop:18}}>{error}</div></div>;
 const customer=data?.customer;const features=data?.features;const insight=data?.insight;
 if(!customer)return <div className="panel empty-state">Customer record not found or access is not permitted.</div>;
 const score=Number(insight?.churn_risk_score||0);
 return <>
  <Link href="/crm" className="link-action"><ArrowLeft size={13} style={{display:"inline",verticalAlign:"-2px"}}/> Back to customer portfolio</Link>
  <div className="profile-top"><div><p className="eyebrow">Relationship management / Customer profile</p><h1 className="page-title">{customer.full_name}</h1><p className="page-subtitle">{customer.email} <span style={{margin:"0 7px",color:"#c0c9d2"}}>·</span>{customer.account_tier} account</p></div><span className={"badge "+(score>=60?"high":score>=30?"medium":"low")} style={{fontSize:11,padding:"8px 12px"}}>Risk score {insight?score.toFixed(1)+" / 100":"Not evaluated"}</span></div>
  <div className="profile-stats">
   <div className="profile-stat"><div className="profile-stat-label"><Activity size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Transactions · 30 days</div><div className="profile-stat-value">{features?.frequency_30d??"—"}</div></div>
   <div className="profile-stat"><div className="profile-stat-label"><Wallet size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Average balance · 30 days</div><div className="profile-stat-value">{features?Number(features.balance_avg_30d).toLocaleString(undefined,{maximumFractionDigits:2}):"—"}</div></div>
   <div className="profile-stat"><div className="profile-stat-label"><CalendarClock size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Activity recency</div><div className="profile-stat-value">{features?features.recency_days+" days":"—"}</div></div>
   <div className="profile-stat"><div className="profile-stat-label"><UserRound size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Salary disruption signal</div><div className="profile-stat-value" style={{fontSize:17}}>{features?.salary_disruption_flag?"Detected":"Not detected"}</div></div>
  </div>
  <section className="panel"><div style={{display:"flex",alignItems:"center",gap:9,marginBottom:15}}><ShieldCheck size={17} color="#177c77"/><h2 className="panel-title">Risk assessment & relationship guidance</h2></div>
   <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:16}}>
    <div><div className="profile-stat-label">Primary risk signal</div><strong style={{display:"block",marginTop:7}}>{insight?.primary_churn_driver||"Not evaluated"}</strong></div>
    <div><div className="profile-stat-label">Transaction velocity</div><strong style={{display:"block",marginTop:7}}>{features?.velocity_score??"—"}</strong></div>
    <div><div className="profile-stat-label">Balance drawdown</div><strong style={{display:"block",marginTop:7}}>{features?Math.round(Number(features.balance_drawdown_pct)*100)+"%":"—"}</strong></div>
    <div><div className="profile-stat-label">Behaviour segment</div><strong style={{display:"block",marginTop:7}}>{features?.behavior_segment?.replaceAll("_"," ")||"—"}</strong></div>
   </div>
   <div style={{marginTop:22,paddingTop:18,borderTop:"1px solid #edf1f4"}}><div className="profile-stat-label">Product for suitability review</div><strong style={{display:"block",marginTop:7,fontSize:15}}>{insight?.recommended_product||"No recommendation available"}</strong></div>
   <div className="explanation-box">{insight?.prescriptive_action||"Run the analytics pipeline to generate a relationship review prompt."}</div>
   <p className="muted" style={{fontSize:10,lineHeight:1.7,margin:"14px 0 0"}}>This is a transparent rule-based assessment, not SHAP or a causal explanation. Treat the score and recommended action as decision support; verify the customer context and complete suitability, eligibility and consent checks before any product discussion.</p>
  </section>
 </>;
}
