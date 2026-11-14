import {NextResponse} from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const base = process.env.SAMORA_API_URL;
  const key = process.env.SAMORA_API_KEY;
  if (!base || !key) return NextResponse.json({error:"The Samora analytics API is not configured."},{status:503});
  try {
    const upstream = await fetch(`${base.replace(/\/$/,"")}/api/v1/model-training/development-segmentation/temporal-stability`, {
      method:"GET",headers:{"X-API-Key":key},cache:"no-store"
    });
    const body = await upstream.json().catch(()=>({error:"The analytics service returned an invalid response."}));
    if (!upstream.ok) {
      const detail = typeof body?.detail === "string" ? body.detail : "Unable to review temporal segment stability.";
      return NextResponse.json({error:detail},{status:upstream.status});
    }
    return NextResponse.json(body,{headers:{"Cache-Control":"no-store"}});
  } catch {
    return NextResponse.json({error:"Unable to reach the Samora analytics service."},{status:502});
  }
}
