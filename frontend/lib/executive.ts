export type ExecutiveOverview={
 generated_at:string;period_days:number;last_pipeline_run:string|null;
 metrics:{transactions_30d:number;debit_volume_30d:number;credit_volume_30d:number;net_flow_30d:number;average_transaction_30d:number;transactions_change_pct:number|null;debit_volume_change_pct:number|null;credit_volume_change_pct:number|null;evaluated_relationships:number;average_risk_score:number;high_risk_relationships:number;high_risk_share_pct:number};
 risk_distribution:{name:string;count:number}[];
 risk_drivers:{name:string;count:number}[];
 transaction_trend:{date:string;transactions:number;debit_volume:number;credit_volume:number}[];
 category_breakdown:{name:string;count:number;volume:number}[];
 channel_breakdown:{name:string;count:number;volume:number}[];
};
export type ExecutiveTransaction={transaction_id:string;reference:string;timestamp:string;amount:number;transaction_type:"Debit"|"Credit";merchant_category:string;channel:string;post_transaction_balance:number};
export async function getExecutiveOverview(period=90):Promise<ExecutiveOverview>{
 const response=await fetch(`/api/executive/overview?period_days=${period}`,{cache:"no-store"});const body=await response.json();if(!response.ok)throw new Error(body.error||"Unable to load executive analytics");return body as ExecutiveOverview;
}
export function number(value:number){return new Intl.NumberFormat("en-US",{maximumFractionDigits:0}).format(value)}
export function amount(value:number){return new Intl.NumberFormat("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}).format(value)}
export function dateTime(value:string){return new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"short"}).format(new Date(value))}
