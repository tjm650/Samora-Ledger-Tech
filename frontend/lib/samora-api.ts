import {NextResponse} from "next/server";
import {requireExecutiveAccess} from "@/lib/auth";

export async function samoraRequest(path:string,init:RequestInit={}){
 const access=await requireExecutiveAccess();
 if(access.response)return access.response;
 const base=process.env.SAMORA_API_URL;const key=process.env.SAMORA_API_KEY;
 if(!base||!key)return NextResponse.json({error:"The Samora API connection is not configured on the server."},{status:503});
 try{
  const headers=new Headers(init.headers);
  headers.set("X-API-Key",key);
  if(access.accessToken)headers.set("Authorization",`Bearer ${access.accessToken}`);
  if(init.body&&!headers.has("Content-Type"))headers.set("Content-Type","application/json");
  const upstream=await fetch(`${(base.endsWith("/")?base.slice(0,-1):base)}${path}`,{...init,headers,cache:"no-store"});
  const text=await upstream.text();
  let body:unknown={};
  try{body=text?JSON.parse(text):{}}catch{body={error:"The analytics service returned an invalid response."}}
  if(!upstream.ok){
   const detail=body&&typeof body==="object"&&"detail" in body?(body as {detail:string}).detail:undefined;
   return NextResponse.json({error:detail||"The analytics service request failed."},{status:upstream.status});
  }
  return NextResponse.json(body,{headers:{"Cache-Control":"no-store"}});
 }catch{
  return NextResponse.json({error:"Unable to reach the Samora analytics service."},{status:502});
 }
}
