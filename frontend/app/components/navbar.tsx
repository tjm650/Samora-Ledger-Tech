"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {useState} from "react";
import {
 Building2,LayoutDashboard,ArrowLeftRight,ShieldAlert,BarChart3,FileText,Scale,
 PanelLeftClose,PanelLeftOpen,X
} from "lucide-react";

const groups=[
 {label:"Overview",items:[
  {href:"/",label:"Executive overview",icon:LayoutDashboard}
 ]},
 {label:"Transaction Management",items:[
  {href:"/transactions",label:"Transaction activity",icon:ArrowLeftRight}
 ]},
 {label:"Risk & Controls",items:[
  {href:"/risk",label:"Risk & exposure",icon:ShieldAlert},
  {href:"/governance",label:"Model governance",icon:Scale}
 ]},
 {label:"Insights & Reporting",items:[
  {href:"/analytics",label:"Analytics & trends",icon:BarChart3},
  {href:"/reports",label:"Management reports",icon:FileText}
 ]}
];

export default function Navbar(){
 const pathname=usePathname();
 const [collapsed,setCollapsed]=useState(false);
 const [mobileOpen,setMobileOpen]=useState(false);
 return <>
  <header className="workspace-header">
   <div className="workspace-header-left">
    <button className="sidebar-toggle desktop-toggle" type="button" onClick={()=>setCollapsed(v=>!v)} aria-label={collapsed?"Expand navigation":"Collapse navigation"} aria-expanded={!collapsed}>
     {collapsed?<PanelLeftOpen size={18}/>:<PanelLeftClose size={18}/>}
    </button>
    <button className="sidebar-toggle mobile-toggle" type="button" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><PanelLeftOpen size={18}/></button>
    <Link href="/" className="workspace-brand" aria-label="Samora Ledger Tech home">
     <span className="brand-mark"><Building2 size={19}/></span>
     <span className="workspace-brand-copy"><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">EXECUTIVE INTELLIGENCE</span></span>
    </Link>
   </div>
   <div className="header-meta"><span className="system-indicator"><span className="status-dot"/>Executive workspace</span></div>
  </header>
  {mobileOpen&&<button className="sidebar-scrim" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}/>}
  <aside className={"workspace-sidebar"+(collapsed?" collapsed":"")+(mobileOpen?" mobile-open":"")} aria-label="Main navigation">
   <div className="sidebar-topline"><span className="sidebar-section-label">WORKSPACE</span><button className="sidebar-close mobile-toggle" type="button" onClick={()=>setMobileOpen(false)} aria-label="Close navigation"><X size={18}/></button></div>
   <nav className="sidebar-nav">
    {groups.map(group=><section className="sidebar-group" key={group.label}>
     <h2 className="sidebar-group-title">{group.label}</h2>
     {group.items.map(item=>{const Icon=item.icon;const active=item.href==="/" ? pathname==="/" : pathname===item.href||pathname.startsWith(item.href+"/");return <Link key={item.href} href={item.href} title={collapsed?item.label:undefined} aria-current={active?"page":undefined} className={"sidebar-link"+(active?" active":"")} onClick={()=>setMobileOpen(false)}><Icon size={17}/><span>{item.label}</span>{active&&<i className="sidebar-active-mark"/>}</Link>})}
    </section>)}
   </nav>
   <div className="sidebar-bottom"><span className="sidebar-bottom-mark"><Building2 size={15}/></span><span className="sidebar-bottom-copy"><strong>Samora Ledger Tech</strong><small>Banking intelligence platform</small></span></div>
  </aside>
 </>;
}
