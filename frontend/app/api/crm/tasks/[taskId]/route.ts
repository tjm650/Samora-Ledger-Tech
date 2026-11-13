import {NextRequest,NextResponse} from "next/server";
import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
export async function PATCH(request:NextRequest,{params}:{params:Promise<{taskId:string}>}){
 const {taskId}=await params;
 try{return await samoraRequest(`/api/v1/crm/tasks/${encodeURIComponent(taskId)}`,{method:"PATCH",body:JSON.stringify(await request.json())})}
 catch{return NextResponse.json({error:"Invalid task update."},{status:400})}
}