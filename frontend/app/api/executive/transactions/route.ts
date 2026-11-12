import {NextRequest,NextResponse} from "next/server";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){
 const base=process.env.SAMORA_API_URL;const key=process.env.SAMORA_API_KEY;
 if(!base||!key)return NextResponse.json({error:"The Samora API connection is not configured on the server."},{status:503});
 const params=new URLSearchParams();for(const name of ["limit","offset","transaction_type","category"]){const value=request.nextUrl.searchParams.get(name);if(value)params.set(name,value)}
 try{const upstream=await fetch(`${base.replace(/\/$/,"")}/api/v1/executive/transactions?${params.toString()}`,{headers:{"X-API-Key":key},cache:"no-store"});const body=await upstream.json();if(!upstream.ok)return NextResponse.json({error:body.detail||"Transaction activity request failed."},{status:upstream.status});return NextResponse.json(body,{headers:{"Cache-Control":"no-store"}})}catch{return NextResponse.json({error:"Unable to reach the Samora analytics service."},{status:502})}
}
