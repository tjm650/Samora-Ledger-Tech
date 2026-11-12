"use client";
import {FormEvent,useState} from "react";
import {useRouter,useSearchParams} from "next/navigation";
import {Building2,LockKeyhole,ShieldCheck} from "lucide-react";
import {createClient} from "@/lib/supabase/client";
const allowedRoles=["admin","analyst","relationship_manager","executive"];
export default function LoginPage(){
 const router=useRouter();const params=useSearchParams();const [email,setEmail]=useState("");const [password,setPassword]=useState("");const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 const reason=params.get("reason");
 async function submit(event:FormEvent<HTMLFormElement>){event.preventDefault();setLoading(true);setError("");try{const supabase=createClient();const {data,error}=await supabase.auth.signInWithPassword({email,password});if(error)throw error;const role=data.user.app_metadata?.role;if(typeof role!=="string"||!allowedRoles.includes(role)){await supabase.auth.signOut();throw new Error("Your account is not assigned an approved banking staff role. Contact your system administrator.")}router.replace(params.get("next")||"/");router.refresh()}catch(e){setError(e instanceof Error?e.message:"Unable to sign in. Please verify your credentials.")}finally{setLoading(false)}}
 const configured=Boolean(process.env.NEXT_PUBLIC_SUPABASE_URL&&(process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY));
 return <div className="login-page"><div className="login-card"><div className="login-brand"><span className="brand-mark"><Building2 size={21}/></span><div><strong>SAMORA LEDGER TECH</strong><span>EXECUTIVE INTELLIGENCE</span></div></div><div className="login-intro"><span className="login-icon"><LockKeyhole size={19}/></span><p className="eyebrow">Secure access</p><h1>Executive sign in</h1><p>Authorised banking personnel can access transaction intelligence, risk oversight and management reporting.</p></div>
  {reason==="configuration"&&!configured&&<div className="alert">Executive authentication is not configured. Add the Supabase project URL and publishable key to the Vercel environment.</div>}
  {reason==="access"&&<div className="alert">Your account is signed in but does not have an approved executive workspace role.</div>}
  {error&&<div className="alert" role="alert">{error}</div>}
  <form onSubmit={submit} className="login-form"><label htmlFor="email">Work email</label><input id="email" type="email" autoComplete="username" required value={email} onChange={e=>setEmail(e.target.value)} placeholder="name@bank.co.zw"/><label htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} placeholder="Enter your password"/><button className="btn login-submit" type="submit" disabled={loading||!configured}>{loading?"Signing in…":"Sign in securely"}</button></form>
  <div className="login-security"><ShieldCheck size={14}/><span>Access is restricted to approved staff accounts. User self-registration is disabled.</span></div>
 </div><p className="login-footer">SAMORA LEDGER TECH · AUTHORISED BUSINESS USE ONLY</p></div>
}
