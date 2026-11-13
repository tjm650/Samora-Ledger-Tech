import {NextRequest,NextResponse} from "next/server";
import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
export async function PATCH(request:NextRequest,{params}:{params:Promise<{alertId:string}>}){
 const {alertId}=await params;
 try{return await samoraRequest(`/api/v1/risk/alerts/${encodeURIComponent(alertId)}`,{method:"PATCH",body:JSON.stringify(await request.json())})}
 catch{return NextResponse.json({error:"Invalid alert update."},{status:400})}
}