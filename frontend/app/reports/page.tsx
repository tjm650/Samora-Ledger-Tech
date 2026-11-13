"use client";
import {useEffect,useState} from "react";
import {Download,Printer,FileBarChart,Calendar} from "lucide-react";
import {amount,getExecutiveOverview,number,type ExecutiveOverview} from "@/lib/executive";
export default function ReportsPage(){
 const [data,setData]=useState<ExecutiveOverview|null>(null);const [loading,setLoading]=useState(true);const [error,setError]=useState("");
 useEffect(()=>{getExecutiveOverview(90).then(setData).catch(e=>setError(e.message||"Unable to prepare management report")).finally(()=>setLoading(false))},[]);
 function exportCsv(){if(!data)return;const rows=[["Samora Ledger Tech","Executive management summary"],["Generated at",data.generated_at],["Reporting period","Latest 90 days"],[],["Indicator","Value"],["Transactions (30 days)",data.metrics.transactions_30d],["Debit volume (30 days)",data.metrics.debit_volume_30d],["Credit volume (30 days)",data.metrics.credit_volume_30d],["Net transaction flow (30 days)",data.metrics.net_flow_30d],["Average transaction (30 days)",data.metrics.average_transaction_30d],["High-risk relationships",data.metrics.high_risk_relationships],["High-risk share (%)",data.metrics.high_risk_share_pct],["Average risk score",data.metrics.average_risk_score],["Relationships evaluated",data.metrics.evaluated_relationships],[],["Risk band","Count"],...data.risk_distribution.map(x=>[x.name,x.count]),[],["Primary risk driver","Count"],...data.risk_drivers.map(x=>[x.name,x.count]),[],["Transaction category","Count","Volume"],...data.category_breakdown.map(x=>[x.name,x.count,x.volume])];const csv=rows.map(row=>row.map(x=>JSON.stringify(x??"")).join(",")).join("\n");const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));const a=document.createElement("a");a.href=url;a.download="samora-executive-management-summary.csv";a.click();URL.revokeObjectURL(url)}
 const m=data?.metrics;
 return <>
  <div className="page-heading page-heading-actions"><div className="heading-actions"><button className="btn btn-secondary" onClick={()=>window.print()} disabled={!data}><Printer size={14}/>Print / Save PDF</button><button className="btn" onClick={exportCsv} disabled={!data}><Download size={14}/>Export report data</button></div></div>
  {error&&<div className="alert" role="alert">{error}</div>}
  {loading?<div className="panel empty-state">Preparing management report…</div>:data&&<>
   <article className="report-sheet"><div className="report-cover"><div><span className="report-brand">SAMORA LEDGER TECH</span><p className="eyebrow" style={{marginTop:28,color:"#8ed0c5"}}>Executive intelligence</p><h2>Management<br/>Performance Brief</h2><p>Transaction activity · Portfolio-level risk · Operational trends</p></div><div className="report-date"><Calendar size={14}/><span>Generated<br/><strong>{new Date(data.generated_at).toLocaleString()}</strong></span></div></div>
    <div className="report-body"><div className="report-section-head"><div><span className="report-kicker">01 / Executive snapshot</span><h3>Key indicators</h3></div><span className="panel-period">LAST 30 DAYS</span></div>
     <div className="report-metric-grid"><div><span>Transaction count</span><strong>{number(m?.transactions_30d||0)}</strong></div><div><span>Debit volume</span><strong>{amount(m?.debit_volume_30d||0)}</strong></div><div><span>Credit volume</span><strong>{amount(m?.credit_volume_30d||0)}</strong></div><div><span>Net transaction flow</span><strong>{amount(m?.net_flow_30d||0)}</strong></div></div>
     <div className="report-section-head"><div><span className="report-kicker">02 / Risk oversight</span><h3>Aggregate risk position</h3></div></div>
     <p className="report-copy">The current scoring run covers <strong>{number(m?.evaluated_relationships||0)}</strong> relationships. The aggregate high-risk band contains <strong>{number(m?.high_risk_relationships||0)}</strong> relationships ({(m?.high_risk_share_pct||0).toFixed(1)}% of those evaluated). The average rules-based score is <strong>{(m?.average_risk_score||0).toFixed(1)} / 100</strong>.</p>
     <div className="report-table-wrap"><table className="table"><thead><tr><th>Risk band</th><th className="numeric">Relationships</th></tr></thead><tbody>{data.risk_distribution.map(x=><tr key={x.name}><td>{x.name}</td><td className="numeric">{number(x.count)}</td></tr>)}</tbody></table></div>
     <div className="report-section-head"><div><span className="report-kicker">03 / Transaction composition</span><h3>Category and activity signals</h3></div><span className="panel-period">90 DAYS</span></div>
     <div className="report-table-wrap"><table className="table"><thead><tr><th>Category</th><th className="numeric">Transactions</th><th className="numeric">Value</th></tr></thead><tbody>{data.category_breakdown.map(x=><tr key={x.name}><td>{x.name}</td><td className="numeric">{number(x.count)}</td><td className="numeric">{amount(x.volume)}</td></tr>)}</tbody></table></div>
     <div className="report-section-head"><div><span className="report-kicker">04 / Management attention</span><h3>Leading risk drivers</h3></div></div>
     <div className="report-driver-list">{data.risk_drivers.slice(0,5).map((x,i)=><div key={x.name}><span>{String(i+1).padStart(2,"0")}</span><strong>{x.name}</strong><b>{number(x.count)}</b></div>)}</div>
     <div className="report-disclaimer"><strong>Basis and limitations</strong><p>Figures are derived from posted transaction records and the latest available rules-based risk evaluation. Currency values remain in the source transaction currency and are not FX-normalised. The risk score is an MVP heuristic, not a validated probability or credit rating. This report is management decision support, not a statutory, prudential or audited financial statement.</p></div>
     <div className="report-end">SAMORA LEDGER TECH <span>CONFIDENTIAL · INTERNAL MANAGEMENT USE</span></div>
    </div>
   </article>
  </>}
 </>;
}
