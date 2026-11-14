import {NextRequest,NextResponse} from "next/server";

export const dynamic="force-dynamic";
type Context={params:Promise<{path:string[]}>};

async function forward(request:NextRequest,context:Context,method:"GET"|"POST"){
 const {path}=await context.params;
 const base=process.env.SAMORA_API_URL;
 const key=process.env.SAMORA_API_KEY;
 if(!base||!key)return NextResponse.json({error:"The Samora API connection is not configured on the server."},{status:503});
 try{
  const headers=new Headers({"X-API-Key":key});
  let body:string|undefined;
  if(method==="POST"){
   body=await request.text();
   headers.set("Content-Type","application/json");
  }
  const upstream=await fetch(`${base.replace(/\/$/,"")}/api/v1/growth/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`,{
   method,headers,body,cache:"no-store"
  });
  const text=await upstream.text();
  let payload:unknown={};
  try{payload=text?JSON.parse(text):{}}catch{payload={error:"The analytics service returned an invalid response."}}
  if(!upstream.ok){
   const detail=payload&&typeof payload==="object"&&"detail" in payload?(payload as {detail:string}).detail:undefined;
   return NextResponse.json({error:detail||"The analytics service request failed."},{status:upstream.status});
  }
  return NextResponse.json(payload,{headers:{"Cache-Control":"no-store"}});
 }catch{
  return NextResponse.json({error:"Unable to reach the Samora analytics service."},{status:502});
 }
}
export async function GET(request:NextRequest,context:Context){return forward(request,context,"GET")}
export async function POST(request:NextRequest,context:Context){return forward(request,context,"POST")}
