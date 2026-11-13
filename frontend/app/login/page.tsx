"use client";

import {FormEvent,useState} from "react";
import {useRouter,useSearchParams} from "next/navigation";
import {createClient} from "@/lib/supabase/client";

export default function LoginPage(){
 const router=useRouter();const search=useSearchParams();
 const [email,setEmail]=useState("");const [password,setPassword]=useState("");
 const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 async function submit(event:FormEvent<HTMLFormElement>){
  event.preventDefault();setError("");setLoading(true);
  try{
   const supabase=createClient();
   const {data,error:signInError}=await supabase.auth.signInWithPassword({email,password});
   if(signInError||!data.user)throw new Error(signInError?.message||"Unable to sign in.");
   const role=data.user.app_metadata?.role;
   if(!["admin","analyst","relationship_manager","executive"].includes(role)){
    await supabase.auth.signOut();throw new Error("This account has not been authorised for Samora Ledger Tech. Contact your administrator.");
   }
   const next=search.get("next");
   router.replace(next&&next.startsWith("/")&&!next.startsWith("//")?next:"/");
   router.refresh();
  }catch(e){setError(e instanceof Error?e.message:"Sign-in failed.");}
  finally{setLoading(false);}
 }
 return <main className="min-h-screen flex items-center justify-center px-5 py-12" style={{background:"var(--background,#f5f7f8)"}}>
  <section className="w-full max-w-md rounded-2xl border bg-white p-8 shadow-sm" style={{borderColor:"#dfe6e8"}}>
   <div className="mb-8"><div className="text-xs font-bold tracking-[.22em] text-teal-700">SAMORA LEDGER TECH</div><h1 className="mt-4 text-2xl font-semibold text-slate-900">Staff sign in</h1><p className="mt-2 text-sm text-slate-600">Access the enterprise banking intelligence workspace using your authorised staff account.</p></div>
   <form onSubmit={submit} className="space-y-4">
    <label className="block text-sm font-medium text-slate-700">Work email<input className="mt-1 w-full rounded-lg border px-3 py-3 text-sm outline-none focus:border-teal-600" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)}/></label>
    <label className="block text-sm font-medium text-slate-700">Password<input className="mt-1 w-full rounded-lg border px-3 py-3 text-sm outline-none focus:border-teal-600" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/></label>
    {error&&<p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
    <button disabled={loading} className="w-full rounded-lg bg-teal-800 px-4 py-3 text-sm font-semibold text-white disabled:opacity-60">{loading?"Signing in…":"Sign in securely"}</button>
   </form>
   <p className="mt-6 text-xs leading-5 text-slate-500">Access is restricted to staff accounts provisioned by an administrator. Public registration is disabled.</p>
  </section>
 </main>;
}
