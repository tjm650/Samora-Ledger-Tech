"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";
import {Building2,LayoutDashboard,ArrowLeftRight,ShieldAlert,BarChart3,FileText,Scale} from "lucide-react";
const links=[
 {href:"/",label:"Executive overview",icon:LayoutDashboard},
 {href:"/transactions",label:"Transactions",icon:ArrowLeftRight},
 {href:"/risk",label:"Risk & exposure",icon:ShieldAlert},
 {href:"/analytics",label:"Analytics",icon:BarChart3},
 {href:"/reports",label:"Management reports",icon:FileText},
 {href:"/governance",label:"Model governance",icon:Scale}
];
export default function Navbar(){
 const pathname=usePathname();
 return <header className="site-header"><div className="header-inner">
  <Link href="/" className="brand" aria-label="Samora Ledger Tech executive workspace home"><span className="brand-mark"><Building2 size={19}/></span><span><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">EXECUTIVE INTELLIGENCE</span></span></Link>
  <nav className="primary-nav" aria-label="Executive navigation">{links.map(item=>{const Icon=item.icon;const active=item.href==="/" ? pathname==="/" : pathname===item.href||pathname.startsWith(item.href+"/");return <Link key={item.href} href={item.href} aria-current={active?"page":undefined} className={"nav-link"+(active?" active":"")}><Icon size={15}/><span>{item.label}</span></Link>})}</nav>
  <div className="header-meta"><span className="system-indicator"><span className="status-dot"/>Executive workspace</span></div>
 </div></header>
}
