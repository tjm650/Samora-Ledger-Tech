import {NextResponse,type NextRequest} from "next/server";

/**
 * Samora is running as a public mock-data demonstration.
 * No browser page or API route requires a Supabase sign-in session.
 * Server-side API credentials remain private in the Next.js server runtime.
 */
export async function middleware(_request:NextRequest){
 return NextResponse.next();
}

export const config={matcher:["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"]};
