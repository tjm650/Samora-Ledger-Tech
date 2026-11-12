"use client";
import {useEffect,useState} from "react";
import {BarChart,Bar,XAxis,YAxis,Tooltip,ResponsiveContainer,PieChart,Pie,Cell} from "recharts";
import Link from "next/link";
type Insight={churn_risk_score:number;primary_churn_driver:string;recommended_product:string};
type Customer={customer_id:string;predictive_insights:Insight[]};
export default function Home(){
 const [rows,setRows]=useState<Customer[]>([]);const [customers,setCustomers]=useState(0);const [error,setError]=useState("");const [loading,setLoading]=useState(true);
 useEffect(()=>{fetch("/api/customers",{cache:"no-store"}).then(async r=>{const body=await r.json();if(!r.ok)throw new Error(body.error||"Unable to load portfolio");return body}).then(body=>{setRows(body.customers||[]);setCustomers(body.count||0)}).catch(e=>setError(e.message||"Unable to load portfolio")).finally(()=>setLoading(false))},[]);
 const insights=rows.map(x=>x.predictive_insights?.[0]).filter(Boolean) as Insight[];
 const high=insights.filter(x=>Number(x.churn_risk_score)>=60).length;
 const opp=insights.filter(x=>x.recommended_product&&x.recommended_product!=="Everyday Banking Bundle").length;
 const avg=insights.length?insights.reduce((a,x)=>a+Number(x.churn_risk_score),0)/insights.length:0;
 const distribution=[{name:"Low",count:insights.filter(x=>x.churn_risk_score<30).length},{name:"Medium",count:insights.filter(x=>x.churn_risk_score>=30&&x.churn_risk_score<60).length},{name:"High",count:high}];
 const drivers=Object.entries(insights.reduce<Record<string,number>>((a,x)=>{a[x.primary_churn_driver]=(a[x.primary_churn_driver]||0)+1;return a},{})).map(([name,value])=>({name,value})).slice(0,6);
 return <><div style={{display:"flex",justifyContent:"space-between",alignItems:"end",marginBottom:26,flexWrap:"wrap",gap:16}}><div><p className="muted">ENTERPRISE ANALYTICS / OVERVIEW</p><h1 style={{fontSize:30,fontWeight:750}}>Executive Overview</h1><p className="muted">Portfolio health, retention exposure and growth opportunities</p></div><Link className="btn" href="/crm">Open customer CRM →</Link></div>
 {error&&<div className="panel" style={{marginBottom:18,color:"#b91c1c"}}>{error}</div>}
 {loading&&<p className="muted">Loading portfolio analytics…</p>}
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(190px,1fr))",gap:16,marginBottom:20}}>{[{label:"Customers",value:customers.toLocaleString()},{label:"High churn risk",value:high.toLocaleString()},{label:"Cross-sell targets",value:opp.toLocaleString()},{label:"Average churn risk",value:avg.toFixed(1)+"%"}].map(x=><div className="panel" key={x.label}><p className="muted" style={{fontSize:13}}>{x.label}</p><strong style={{fontSize:29}}>{x.value}</strong></div>)}</div>
 <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(300px,1fr))",gap:18}}><section className="panel"><h2 style={{fontWeight:700,marginBottom:18}}>Churn Risk Distribution</h2><div style={{height:280}}><ResponsiveContainer><BarChart data={distribution}><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" fill="#0f766e" radius={[6,6,0,0]}/></BarChart></ResponsiveContainer></div></section><section className="panel"><h2 style={{fontWeight:700,marginBottom:18}}>Primary Risk Drivers</h2><div style={{height:280}}><ResponsiveContainer><PieChart><Pie data={drivers} dataKey="value" nameKey="name" outerRadius={100} label>{drivers.map((_,i)=><Cell key={i} fill={["#0f766e","#2563eb","#d97706","#dc2626","#7c3aed","#64748b"][i%6]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer></div></section></div>
 <p className="muted" style={{fontSize:12,marginTop:20}}>Scores are demonstrative heuristics, not validated predictions. Revenue at risk is not estimated until customer-level revenue / margin data is integrated.</p></>;
}
