import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
export async function GET(_request:Request,{params}:{params:Promise<{customerId:string}>}){
 const {customerId}=await params;
 return samoraRequest(`/api/v1/crm/customers/${encodeURIComponent(customerId)}`);
}