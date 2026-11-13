import {NextRequest} from "next/server";
import {samoraRequest} from "@/lib/samora-api";
export const dynamic="force-dynamic";
export async function GET(request:NextRequest){return samoraRequest(`/api/v1/risk/trends${request.nextUrl.search}`)}