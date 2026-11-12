"use client";
import Link from "next/link";
import {usePathname,useRouter} from "next/navigation";
import {useEffect,useState} from "react";
import {createBrowserClient} from "@supabase/ssr";
import {Building2,LayoutDashboard,ArrowLeftRight,ShieldAlert,BarChart3,FileText,Scale,LogOut} from "lucide-react";
const links=[
 {href:"/",label:"Executive overview",icon:LayoutDashboard},
 {href:"/transactions",label:"Transactions",icon:ArrowLeftRight},
 {href:"/risk",label:"Risk & exposure",icon:ShieldAlert},
 {href:"/analytics",label:"Analytics",icon:BarChart3},
 {href:"/reports",label:"Management reports",icon:FileText},
 {href:"/governance",label:"Model governance",icon:Scale}
];
export default function Navbar(){
 const pathname=usePathname();const router=useRouter();const [email,setEmail]=useState("");
 useEffect(()=>{const url=process.env.NEXT_PUBLIC_SUPABASE_URL;const key=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;if(!url||!key||pathname==="/login")return;const supabase=createBrowserClient(url,key);supabase.auth.getUser().then(({data})=>setEmail(data.user?.email||""));const {data:{subscription}}=supabase.auth.onAuthStateChange((_event,session)=>setEmail(session?.user.email||""));return()=>subscription.unsubscribe()},[pathname]);
 if(pathname==="/login")return null;
 async function signOut(){const url=process.env.NEXT_PUBLIC_SUPABASE_URL;const key=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY||process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;if(url&&key){const supabase=createBrowserClient(url,key);await supabase.auth.signOut()}router.replace("/login");router.refresh()}
 return <header className="site-header"><div className="header-inner">
  <Link href="/" className="brand" aria-label="Samora Ledger Tech executive workspace home"><span className="brand-mark"><Building2 size={19}/></span><span><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">EXECUTIVE INTELLIGENCE</span></span></Link>
  <nav className="primary-nav" aria-label="Executive navigation">{links.map(item=>{const Icon=item.icon;const active=item.href==="/" ? pathname==="/" : pathname===item.href||pathname.startsWith(item.href+"/");return <Link key={item.href} href={item.href} aria-current={active?"page":undefined} className={"nav-link"+(active?" active":"")}><Icon size={15}/><span>{item.label}</span></Link>})}</nav>
  <div className="header-meta">{email&&<><span className="system-indicator"><span className="status-dot"/>Executive access</span><button className="signout-button" onClick={signOut} aria-label="Sign out"><LogOut size={14}/><span>Sign out</span></button></>}</div>
 </div></header>
}
