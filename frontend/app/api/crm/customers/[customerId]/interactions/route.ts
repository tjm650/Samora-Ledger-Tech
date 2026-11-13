import {NextRequest,NextResponse} from "next/server";
import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest,{params}:{params:Promise<{customerId:string}>}){
 const {customerId}=await params;
 return samoraRequest(`/api/v1/crm/customers/${encodeURIComponent(customerId)}/interactions${request.nextUrl.search}`);
}
export async function POST(request:NextRequest,{params}:{params:Promise<{customerId:string}>}){
 const {customerId}=await params;
 try{return await samoraRequest(`/api/v1/crm/customers/${encodeURIComponent(customerId)}/interactions`,{method:"POST",body:JSON.stringify(await request.json())})}
 catch{return NextResponse.json({error:"Invalid interaction request."},{status:400})}
}