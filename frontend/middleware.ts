import {NextResponse,type NextRequest} from "next/server";
import {updateSession} from "@/lib/supabase/proxy";

/**
 * Demo-mode page access: the sign-in screen and page redirects are suspended.
 * API routes still pass through the existing Supabase session/role checks.
 * This intentionally does not make protected banking data APIs public.
 */
export async function middleware(request:NextRequest){
 const {pathname}=request.nextUrl;
 if(pathname==="/login"){
  const target=request.nextUrl.clone();
  target.pathname="/";
  target.search="";
  return NextResponse.redirect(target);
 }
 if(!pathname.startsWith("/api/"))return NextResponse.next();
 // Public demo mode applies only to GET requests. Route handlers and the backend
 // independently enforce staff authorization for writes and privileged reads.
 if(process.env.SAMORA_DEMO_PUBLIC_READS==="true"&&request.method==="GET")return NextResponse.next();
 return updateSession(request);
}

export const config={matcher:["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"]};
