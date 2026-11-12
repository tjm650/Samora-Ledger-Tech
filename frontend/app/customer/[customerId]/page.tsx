"use client";
import {useEffect,useState} from "react";
import Link from "next/link";
import {useParams} from "next/navigation";
import {ArrowLeft,ShieldCheck,Activity,Wallet,CalendarClock,UserRound} from "lucide-react";

type Payload={customer:{customer_id:string;full_name:string;email:string;account_tier:string;created_at:string};features:Record<string,unknown>|null;insight:{churn_risk_score:number;primary_churn_driver:string;recommended_product:string;prescriptive_action:string;evaluated_at:string}|null;explanation_type:string};
const labels:Record<string,string>={recency_days:"Days since last transaction",frequency_30d:"Transactions in last 30 days",monetary_spend_90d:"Debit spend in last 90 days",balance_avg_30d:"Average balance (30 days)",velocity_score:"Transaction velocity",discretionary_spend_ratio:"Discretionary spend ratio",salary_disruption_flag:"Salary disruption detected",balance_drawdown_pct:"Balance drawdown",behavior_segment:"Behaviour segment"};
export default function CustomerDetail(){
 const params=useParams<{customerId:string}>();const id=params.customerId;const [data,setData]=useState<Payload|null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 useEffect(()=>{if(!id)return;fetch("/api/customers/"+encodeURIComponent(id),{cache:"no-store"}).then(async r=>{const body=await r.json();if(!r.ok)throw new Error(body.error||"Unable to load customer");return body}).then(setData).catch(e=>setError(e.message||"Unable to load customer")).finally(()=>setLoading(false))},[id]);
 const f=data?.features;const i=data?.insight;const fmt=(key:string,value:unknown)=>typeof value==="number"?(key.includes("ratio")||key.includes("pct")?(value*100).toFixed(1)+"%":Number.isInteger(value)?String(value):value.toFixed(2)):typeof value==="boolean"?(value?"Yes":"No"):String(value??"—");
 if(loading)return <div className="panel empty-state">Loading customer profile…</div>;
 if(error)return <div><Link href="/crm" className="link-action"><ArrowLeft size={13} style={{display:"inline"}}/> Back to portfolio</Link><div className="alert" style={{marginTop:18}}>{error}</div></div>;
 if(!data)return <div className="panel empty-state">Customer record not found or access is not permitted.</div>;
 const score=Number(i?.churn_risk_score??0);
 return <>
  <Link href="/crm" className="link-action"><ArrowLeft size={13} style={{display:"inline",verticalAlign:"-2px"}}/> Back to customer portfolio</Link>
  <div className="profile-top"><div><p className="eyebrow">Relationship management / Customer profile</p><h1 className="page-title">{data.customer.full_name}</h1><p className="page-subtitle">{data.customer.email} <span style={{margin:"0 7px",color:"#c0c9d2"}}>·</span>{data.customer.account_tier} account</p></div><span className={"badge "+(score>=60?"high":score>=30?"medium":"low")} style={{fontSize:11,padding:"8px 12px"}}>Risk score {i?score.toFixed(1)+" / 100":"Not evaluated"}</span></div>
  <div className="profile-stats">
   <div className="profile-stat"><div className="profile-stat-label"><Activity size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Transactions · 30 days</div><div className="profile-stat-value">{f?.frequency_30d!==undefined?fmt("frequency_30d",f.frequency_30d):"—"}</div></div>
   <div className="profile-stat"><div className="profile-stat-label"><Wallet size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Average balance · 30 days</div><div className="profile-stat-value">{f?.balance_avg_30d!==undefined?fmt("balance_avg_30d",f.balance_avg_30d):"—"}</div></div>
   <div className="profile-stat"><div className="profile-stat-label"><CalendarClock size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Activity recency</div><div className="profile-stat-value">{f?.recency_days!==undefined?fmt("recency_days",f.recency_days)+" days":"—"}</div></div>
   <div className="profile-stat"><div className="profile-stat-label"><UserRound size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Salary disruption signal</div><div className="profile-stat-value" style={{fontSize:17}}>{f?.salary_disruption_flag!==undefined?fmt("salary_disruption_flag",f.salary_disruption_flag):"—"}</div></div>
  </div>
  <section className="panel"><div style={{display:"flex",alignItems:"center",gap:9,marginBottom:15}}><ShieldCheck size={17} color="#177c77"/><h2 className="panel-title">Risk assessment & relationship guidance</h2></div>
   <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:16}}>
    <div><div className="profile-stat-label">Primary risk signal</div><strong style={{display:"block",marginTop:7}}>{i?.primary_churn_driver||"Not evaluated"}</strong></div>
    <div><div className="profile-stat-label">Transaction velocity</div><strong style={{display:"block",marginTop:7}}>{f?.velocity_score!==undefined?fmt("velocity_score",f.velocity_score):"—"}</strong></div>
    <div><div className="profile-stat-label">Balance drawdown</div><strong style={{display:"block",marginTop:7}}>{f?.balance_drawdown_pct!==undefined?fmt("balance_drawdown_pct",f.balance_drawdown_pct):"—"}</strong></div>
    <div><div className="profile-stat-label">Behaviour segment</div><strong style={{display:"block",marginTop:7}}>{f?.behavior_segment?String(f.behavior_segment).replaceAll("_"," "):"—"}</strong></div>
   </div>
   <div style={{marginTop:22,paddingTop:18,borderTop:"1px solid #edf1f4"}}><div className="profile-stat-label">Product for suitability review</div><strong style={{display:"block",marginTop:7,fontSize:15}}>{i?.recommended_product||"No recommendation available"}</strong></div>
   <div className="explanation-box">{i?.prescriptive_action||"Run the analytics pipeline to generate a relationship review prompt."}</div>
   <p className="muted" style={{fontSize:10,lineHeight:1.7,margin:"14px 0 0"}}>This is a transparent rule-based assessment, not SHAP or a causal explanation. Treat the score and recommended action as decision support; verify the customer context and complete suitability, eligibility and consent checks before any product discussion.</p>
  </section>
  <section className="panel" style={{marginTop:18}}><h2 className="panel-title" style={{marginBottom:14}}>Behavioural features</h2><div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(210px,1fr))",gap:11}}>{Object.entries(f||{}).filter(([k])=>k!=="customer_id"&&k!=="updated_at"&&k!=="frequency_30d"&&k!=="balance_avg_30d"&&k!=="recency_days"&&k!=="salary_disruption_flag").map(([k,v])=><div key={k} className="profile-stat"><div className="profile-stat-label">{labels[k]||k.replaceAll("_"," ")}</div><strong style={{display:"block",marginTop:8}}>{fmt(k,v)}</strong></div>)}</div></section>
  <p className="muted" style={{fontSize:10,lineHeight:1.7,marginTop:15}}>Explanation method: {data.explanation_type}. The current scoring approach is a transparent rules-based baseline, not a validated production machine-learning model.</p>
 </>;
}
