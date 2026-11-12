import {NextResponse} from "next/server";

export const dynamic="force-dynamic";

export async function POST(){
 const baseUrl=process.env.SAMORA_API_URL;
 const apiKey=process.env.SAMORA_API_KEY;
 if(!baseUrl||!apiKey)return NextResponse.json({error:"The Samora API connection is not configured on the server."},{status:503});
 try{
  const upstream=await fetch(`${baseUrl.replace(/\/$/,"")}/api/v1/run-pipeline`,{method:"POST",headers:{"X-API-Key":apiKey},cache:"no-store"});
  const body=await upstream.json();
  if(!upstream.ok)return NextResponse.json({error:body.detail||"Analytics pipeline request failed."},{status:upstream.status});
  return NextResponse.json(body,{headers:{"Cache-Control":"no-store"}});
 }catch{return NextResponse.json({error:"Unable to reach the Samora analytics service."},{status:502});}
}
