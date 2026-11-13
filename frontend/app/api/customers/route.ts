import {NextResponse} from "next/server";
import {requireExecutiveAccess} from "@/lib/auth";
export const dynamic="force-dynamic";
export async function GET(){
 const access=await requireExecutiveAccess();if(access.response)return access.response;
 const base=process.env.SAMORA_API_URL;const key=process.env.SAMORA_API_KEY;
 if(!base||!key)return NextResponse.json({error:"The Samora API connection is not configured on the server."},{status:503});
 try{const upstream=await fetch(`${base.replace(/\/$/,"")}/api/v1/customers`,{headers:{"X-API-Key":key,...(access.accessToken?{Authorization:`Bearer ${access.accessToken}`}:{})},cache:"no-store"});const body=await upstream.json();if(!upstream.ok)return NextResponse.json({error:body.detail||"Customer request failed."},{status:upstream.status});return NextResponse.json(body,{headers:{"Cache-Control":"no-store"}})}catch{return NextResponse.json({error:"Unable to reach the Samora analytics service."},{status:502})}
}