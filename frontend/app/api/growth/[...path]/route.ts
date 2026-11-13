import {NextRequest} from "next/server";
import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
type Context={params:Promise<{path:string[]}>};
export async function GET(request:NextRequest,context:Context){const {path}=await context.params;return samoraRequest(`/api/v1/growth/${path.join("/")}${request.nextUrl.search}`)}
export async function POST(request:NextRequest,context:Context){const {path}=await context.params;const body=await request.text();return samoraRequest(`/api/v1/growth/${path.join("/")}`,{method:"POST",headers:{"Content-Type":"application/json"},body:body||undefined})}
