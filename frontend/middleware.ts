import {NextResponse,type NextRequest} from "next/server";

// Temporary open-access mode for the executive workspace.
// Restore the Supabase session and role checks before production use.
export function middleware(_request:NextRequest){return NextResponse.next()}

export const config={matcher:["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"]};
