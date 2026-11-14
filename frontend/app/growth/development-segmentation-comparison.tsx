"use client";

import {useEffect,useState} from "react";
import {RefreshCw,Info} from "lucide-react";

type Candidate={
  cluster_count:number;silhouette_mean:number|null;silhouette_std:number|null;
  stability_ari_mean:number|null;stability_ari_min:number|null;
  representative_cluster_sizes:number[];smallest_cluster_share_pct:number;
  clusters_below_2pct:number;
};
type Comparison={
  status:string;customers_evaluated:number;random_seeds:number[];
  comparison:Candidate[];interpretation_note:string;
};
const fmt=(value:number|null|undefined)=>value==null?"—":value.toFixed(3);
export default function DevelopmentSegmentationComparison({enabled=true}:{enabled?:boolean}){
  const [data,setData]=useState<Comparison|null>(null);
  const [loading,setLoading]=useState(true);
  const [error,setError]=useState("");
  async function load(){
    setLoading(true);setError("");
    try{
      const response=await fetch("/api/model-training/development-segmentation/compare",{cache:"no-store"});
      const body=await response.json();
      if(!response.ok)throw new Error(body.error||"Unable to compare segmentation candidates.");
      setData(body);
    }catch(e){setError(e instanceof Error?e.message:"Unable to compare segmentation candidates.");}
    finally{setLoading(false);}
  }
  useEffect(()=>{if(enabled&&!data)void load();},[enabled]);
  return <section className="panel" style={{marginTop:18,boxShadow:"none"}}>
    <div className="panel-heading">
      <div><h3 className="panel-title">Cluster-count stability review</h3><p className="panel-caption">Read-only comparison of 2–5 clusters across repeated initialisations</p></div>
      <button className="btn" onClick={()=>void load()} disabled={loading}><RefreshCw size={14}/>{loading?"Comparing…":"Refresh comparison"}</button>
    </div>
    <div className="governance-callout" role="note"><Info size={15}/> Same mock snapshot, feature set and preprocessing for every candidate. Five fixed random seeds per cluster count; no model registry or customer data is changed.</div>
    {error&&<div className="governance-callout" role="alert">{error}</div>}
    {loading&&!data?<div className="empty-state">Evaluating cluster-count candidates…</div>:null}
    {data&&<>
      <div className="table-scroll" style={{marginTop:12}}>
        <table className="table"><thead><tr><th>Clusters</th><th>Silhouette mean ± SD</th><th>Seed stability · ARI</th><th>Smallest cluster</th><th>Clusters under 2%</th><th>Seed 42 sizes</th></tr></thead>
          <tbody>{data.comparison.map(candidate=><tr key={candidate.cluster_count}>
            <td><strong>{candidate.cluster_count}</strong></td>
            <td>{fmt(candidate.silhouette_mean)} ± {fmt(candidate.silhouette_std)}</td>
            <td>{fmt(candidate.stability_ari_mean)} mean · {fmt(candidate.stability_ari_min)} min</td>
            <td>{candidate.smallest_cluster_share_pct.toFixed(2)}%</td>
            <td>{candidate.clusters_below_2pct}</td>
            <td>{candidate.representative_cluster_sizes.join(" / ")}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p className="governance-note">{data.customers_evaluated.toLocaleString("en-US")} quality-passed mock customers · Seeds: {data.random_seeds.join(", ")}. {data.interpretation_note}</p>
    </>}
  </section>;
}
