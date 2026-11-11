export type Customer = {customer_id:string;full_name:string;email:string;account_tier:string};
export type Insight = {customer_id:string;churn_risk_score:number;primary_churn_driver:string;recommended_product:string;prescriptive_action:string};
export type CustomerRow = Customer & {predictive_insights:Insight[]};
