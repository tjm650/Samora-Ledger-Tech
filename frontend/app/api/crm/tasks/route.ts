import {NextRequest,NextResponse} from "next/server";
import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){return samoraRequest(`/api/v1/crm/tasks${request.nextUrl.search}`)}
export async function POST(request:NextRequest){
 try{return await samoraRequest("/api/v1/crm/tasks",{method:"POST",body:JSON.stringify(await request.json())})}
 catch{return NextResponse.json({error:"Invalid task request."},{status:400})}
}