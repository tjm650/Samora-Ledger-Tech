import {NextResponse} from "next/server";
import {createClient} from "@/lib/supabase/server";

const allowedRoles=["admin","analyst","relationship_manager","executive"];

export async function requireExecutiveAccess(method="GET"){
 if(method.toUpperCase()==="GET"&&process.env.SAMORA_DEMO_PUBLIC_READS==="true")return {response:null,user:null,accessToken:null,role:"demo"};
 try{
  const supabase=await createClient();
  const {data:{user},error}=await supabase.auth.getUser();
  if(error||!user)return {response:NextResponse.json({error:"Executive sign-in required."},{status:401}),user:null,accessToken:null};
  const role=user.app_metadata?.role;
  if(typeof role!=="string"||!allowedRoles.includes(role)){
   return {response:NextResponse.json({error:"Your account is not authorised for the executive workspace."},{status:403}),user:null,accessToken:null};
  }
  const {data:{session}}=await supabase.auth.getSession();
  if(!session?.access_token)return {response:NextResponse.json({error:"Your staff session has expired. Please sign in again."},{status:401}),user:null,accessToken:null};
  return {response:null,user,accessToken:session.access_token,role};
 }catch{
  return {response:NextResponse.json({error:"Executive authentication is not configured correctly."},{status:503}),user:null,accessToken:null};
 }
}
