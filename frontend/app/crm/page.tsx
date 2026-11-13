"use client";
import Link from "next/link";
import HeaderActions from "@/app/components/header-actions";
import {useEffect,useState} from "react";
import {Search,Users,RefreshCw,ArrowUpRight} from "lucide-react";
type Customer={customer_id:string;full_name:string;email?:string;account_tier?:string;created_at?:string;churn_risk_score?:number|null;primary_churn_driver?:string;recommended_product?:string;prescriptive_action?:string;behavior_segment?:string};
type Directory={customers:Customer[];total:number;page:number;page_size:number};
function riskBand(score:number){return score>=60?"high":score>=30?"medium":"low"}
export default function CRM(){
 const [customers,setCustomers]=useState<Customer[]>([]);const [loading,setLoading]=useState(true);const [error,setError]=useState("");const [search,setSearch]=useState("");const [risk,setRisk]=useState("all");const [tier,setTier]=useState("all");const [segment,setSegment]=useState("all");const [sort,setSort]=useState("name");const [direction,setDirection]=useState("asc");const [createdFrom,setCreatedFrom]=useState("");const [createdTo,setCreatedTo]=useState("");const [page,setPage]=useState(1);const [total,setTotal]=useState(0);const pageSize=50;
 async function load(){
  setLoading(true);setError("");
  try{
   const params=new URLSearchParams({page:String(page),page_size:String(pageSize),sort_by:sort,sort_dir:direction});
   if(search.trim())params.set("search",search.trim());
   if(risk!=="all")params.set("risk_band",risk==="medium"?"moderate":risk);
   if(tier!=="all")params.set("account_tier",tier);
   if(segment!=="all")params.set("segment",segment);
   if(createdFrom)params.set("created_from",createdFrom);
   if(createdTo)params.set("created_to",createdTo);
   const response=await fetch(`/api/crm/customers?${params.toString()}`,{cache:"no-store"});
   const body=await response.json();if(!response.ok)throw new Error(body.error||"Unable to load customers");
   const result=body as Directory;setCustomers(result.customers||[]);setTotal(result.total||0);
  }catch(e){setError(e instanceof Error?e.message:"Unable to load customers")}finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[search,risk,tier,segment,sort,direction,createdFrom,createdTo,page]);
 useEffect(()=>{setPage(1)},[search,risk,tier,segment,sort,direction,createdFrom,createdTo]);
 const high=customers.filter(c=>(c.churn_risk_score??-1)>=60).length;
 return <><HeaderActions><div className="heading-actions"><button className="btn btn-secondary" onClick={()=>void load()} disabled={loading}><RefreshCw size={14}/>Refresh</button></div></HeaderActions>
 {error&&<div className="alert" role="alert">{error}</div>}
 <div className="kpi-grid kpi-three"><div className="kpi-card"><div className="kpi-label"><Users size={14} style={{display:"inline",marginRight:7}}/>Matching customer records</div><div className="kpi-value">{loading?"—":total.toLocaleString()}</div><div className="kpi-note">Server-side matching records</div></div><div className="kpi-card"><div className="kpi-label">High-risk relationships</div><div className="kpi-value">{loading?"—":high.toLocaleString()}</div><div className="kpi-note">High-risk records on this page</div></div><div className="kpi-card"><div className="kpi-label">Profiles displayed</div><div className="kpi-value">{loading?"—":customers.length.toLocaleString()}</div><div className="kpi-note">Current result page</div></div></div>
 <section className="panel"><div className="panel-heading" style={{marginBottom:18}}><div><h2 className="panel-title">Customer directory</h2><p className="panel-caption">Search, filter and sort customer relationships using server-side records</p></div></div>
 <div className="table-toolbar"><label className="search-field"><Search size={15}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, email or customer ID"/></label>
 <select className="filter-select" value={risk} onChange={e=>setRisk(e.target.value)} aria-label="Filter by risk"><option value="all">All risk levels</option><option value="high">High risk</option><option value="medium">Moderate risk</option><option value="low">Low risk</option></select>
 <select className="filter-select" value={tier} onChange={e=>setTier(e.target.value)} aria-label="Filter by account tier"><option value="all">All account tiers</option><option value="Standard">Standard</option><option value="Gold">Gold</option><option value="Platinum">Platinum</option></select>
 <select className="filter-select" value={segment} onChange={e=>setSegment(e.target.value)} aria-label="Filter by segment"><option value="all">All segments</option><option value="engaged">Engaged</option><option value="low_engagement">Low engagement</option><option value="salary_disrupted">Salary disrupted</option></select>
 <select className="filter-select" value={sort} onChange={e=>setSort(e.target.value)} aria-label="Sort customers"><option value="name">Sort: Name</option><option value="risk_score">Sort: Risk score</option><option value="account_tier">Sort: Account tier</option><option value="created_at">Sort: Created date</option></select>
 <select className="filter-select" value={direction} onChange={e=>setDirection(e.target.value)} aria-label="Sort direction"><option value="asc">Ascending</option><option value="desc">Descending</option></select>
 </div>
 <div className="table-toolbar" style={{marginTop:10}}><label className="search-field"><span>Created from</span><input aria-label="Created from" type="date" value={createdFrom} onChange={e=>setCreatedFrom(e.target.value)}/></label><label className="search-field"><span>Created to</span><input aria-label="Created to" type="date" value={createdTo} onChange={e=>setCreatedTo(e.target.value)}/></label></div>
 <div className="table-scroll"><table className="table executive-table"><thead><tr><th>Customer</th><th>Account tier</th><th>Behaviour segment</th><th>Risk score</th><th>Primary risk driver</th><th>Recommended product</th><th></th></tr></thead><tbody>{customers.map(c=>{const score=c.churn_risk_score;return <tr key={c.customer_id}><td><div className="customer-name">{c.full_name||"Unnamed customer"}</div><div className="customer-email">{c.email||c.customer_id}</div></td><td>{c.account_tier||"—"}</td><td>{c.behavior_segment||"—"}</td><td>{score===undefined||score===null?<span className="badge neutral">Not scored</span>:<span className={"badge "+riskBand(score)}>{score.toFixed(1)} / 100</span>}</td><td>{c.primary_churn_driver||"—"}</td><td>{c.recommended_product||"—"}</td><td><Link className="link-action" href={`/customer/${encodeURIComponent(c.customer_id)}`}>View profile <ArrowUpRight size={12} style={{display:"inline",verticalAlign:"-2px"}}/></Link></td></tr>})}{!loading&&customers.length===0&&<tr><td colSpan={7}><div className="empty-state">No customer records match the current search and filters.</div></td></tr>}{loading&&<tr><td colSpan={7}><div className="empty-state">Loading customer records…</div></td></tr>}</tbody></table></div>
 <div className="pagination"><span>Showing {total===0?0:(page-1)*pageSize+1}–{Math.min(page*pageSize,total)} of {total.toLocaleString()} customers</span><div className="heading-actions"><button className="btn btn-secondary" disabled={loading||page<=1} onClick={()=>setPage(p=>Math.max(1,p-1))}>Previous</button><span>Page {page} of {Math.max(1,Math.ceil(total/pageSize))}</span><button className="btn btn-secondary" disabled={loading||page>=Math.ceil(total/pageSize)} onClick={()=>setPage(p=>p+1)}>Next</button></div></div></section>
 <p className="governance-note">Risk scores are transparent rules-based indicators for decision support, not validated production predictions. Customer information is confidential and available only to authorised banking personnel.</p></>;
}
