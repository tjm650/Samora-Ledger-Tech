"use client";
import Link from "next/link";
import {usePathname} from "next/navigation";
import {Building2,LayoutDashboard,Users} from "lucide-react";

export default function Navbar(){
 const pathname=usePathname();
 const links=[{href:"/",label:"Executive Overview",icon:LayoutDashboard},{href:"/crm",label:"Customer Portfolio",icon:Users}];
 return <header className="site-header"><div className="header-inner">
  <Link href="/" className="brand" aria-label="Samora Ledger Tech home"><span className="brand-mark"><Building2 size={19}/></span><span><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">BANKING INTELLIGENCE</span></span></Link>
  <nav className="primary-nav" aria-label="Main navigation">{links.map(item=>{const Icon=item.icon;const active=item.href==="/" ? pathname==="/" : pathname.startsWith(item.href)||pathname.startsWith("/customer/");return <Link key={item.href} href={item.href} className={"nav-link"+(active?" active":"")}><Icon size={15}/>{item.label}</Link>})}</nav>
  <div className="header-meta"><span className="system-indicator"><span className="status-dot"/>Analytics workspace</span></div>
 </div></header>
}
