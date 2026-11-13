import {NextResponse,type NextRequest} from "next/server";
import {updateSession} from "@/lib/supabase/proxy";

/**
 * Demo access controls:
 * - SAMORA_BYPASS_SIGNIN=true makes all frontend pages public and redirects
 *   known sign-in URLs to the dashboard.
 * - SAMORA_DEMO_PUBLIC_READS=true separately permits public GET API requests.
 *
 * API writes and privileged backend operations retain their existing
 * authorization checks; bypassing the UI sign-in is not an API write bypass.
 */
const signInPaths=new Set(["/login","/signin","/sign-in","/auth/login"]);

export async function middleware(request:NextRequest){
 const {pathname}=request.nextUrl;
 const bypassSignin=process.env.SAMORA_BYPASS_SIGNIN==="true";

 if(bypassSignin&&signInPaths.has(pathname)){
  const target=request.nextUrl.clone();
  target.pathname="/";
  target.search="";
  return NextResponse.redirect(target);
 }

 // The executive demo is intentionally browseable without a Supabase session.
 // API access is controlled separately below.
 if(bypassSignin&&!pathname.startsWith("/api/"))return NextResponse.next();

 if(!pathname.startsWith("/api/"))return NextResponse.next();

 // Public demo mode applies only to GET requests. Route handlers and the backend
 // independently enforce staff authorization for writes and privileged reads.
 if(process.env.SAMORA_DEMO_PUBLIC_READS==="true"&&request.method==="GET")return NextResponse.next();
 return updateSession(request);
}

export const config={matcher:["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"]};
