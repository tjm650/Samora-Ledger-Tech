import {createServerClient} from "@supabase/ssr";
import {NextResponse,type NextRequest} from "next/server";
const allowedRoles=["admin","analyst","relationship_manager","executive"];
export async function updateSession(request:NextRequest){
 const url=process.env.NEXT_PUBLIC_SUPABASE_URL;
 const key=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
 const pathname=request.nextUrl.pathname;
 if(!url||!key){
  if(pathname==="/login")return NextResponse.next({request});
  if(pathname.startsWith("/api/"))return NextResponse.json({error:"Executive authentication is not configured."},{status:503});
  const target=request.nextUrl.clone();target.pathname="/login";target.searchParams.set("reason","configuration");return NextResponse.redirect(target);
 }
 let response=NextResponse.next({request});
 const supabase=createServerClient(url,key,{cookies:{getAll(){return request.cookies.getAll()},setAll(cookiesToSet){cookiesToSet.forEach(({name,value})=>request.cookies.set(name,value));response=NextResponse.next({request});cookiesToSet.forEach(({name,value,options})=>response.cookies.set(name,value,options))}}});
 const {data:{claims}}=await supabase.auth.getClaims();
 const role=(claims?.app_metadata as Record<string,unknown>|undefined)?.role;
 const authorised=Boolean(claims&&typeof role==="string"&&allowedRoles.includes(role));
 if(pathname==="/login"){if(authorised){const target=request.nextUrl.clone();target.pathname="/";target.search="";return NextResponse.redirect(target)}return response}
 if(!authorised){
  if(pathname.startsWith("/api/"))return NextResponse.json({error:claims?"Your account is not authorised for the executive workspace.":"Executive sign-in required."},{status:claims?403:401});
  const target=request.nextUrl.clone();target.pathname="/login";target.searchParams.set("next",pathname);if(claims)target.searchParams.set("reason","access");return NextResponse.redirect(target);
 }
 return response;
}
