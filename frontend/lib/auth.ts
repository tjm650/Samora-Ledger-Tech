import {NextResponse} from "next/server";
import {createClient} from "@/lib/supabase/server";
const allowedRoles=["admin","analyst","relationship_manager","executive"];
export async function requireExecutiveAccess(){
 try{
  const supabase=await createClient();
  const {data:{user},error}=await supabase.auth.getUser();
  if(error||!user)return {response:NextResponse.json({error:"Executive sign-in required."},{status:401})};
  const role=user.app_metadata?.role;
  if(typeof role!=="string"||!allowedRoles.includes(role))return {response:NextResponse.json({error:"Your account is not authorised for the executive workspace."},{status:403})};
  return {response:null,user};
 }catch{return {response:NextResponse.json({error:"Executive authentication is not configured."},{status:503})}}
}
