"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {useState} from "react";
import {
 LayoutDashboard,ArrowLeftRight,ShieldAlert,BarChart3,FileText,Scale,Users,ShoppingBag,UserRound,
 Menu,X,HelpCircle,Settings,RefreshCw,Activity
} from "lucide-react";

const navItems=[
 {href:"/",label:"Overview",icon:LayoutDashboard},
 {href:"/assistant",label:"AI Employee",icon:UserRound},
 {href:"/crm",label:"CRM",icon:Users},
 {href:"/transactions",label:"Transaction activity",icon:ArrowLeftRight},
 {href:"/risk",label:"Risks",icon:ShieldAlert},
 {href:"/governance",label:"Model governance",icon:Scale},
 {href:"/growth",label:"Growth intelligence",icon:ShoppingBag},
 {href:"/analytics",label:"Analytics",icon:BarChart3},
 {href:"/reports",label:"Management reports",icon:FileText},
 {href:"/help",label:"Help",icon:HelpCircle},
 {href:"/settings",label:"Settings",icon:Settings}
];

export default function Navbar(){
 const pathname=usePathname();
 const [mobileOpen,setMobileOpen]=useState(false);
 const [navDismissed,setNavDismissed]=useState(false);

 return <>
  <header className="workspace-header">
   <div className="workspace-header-left">
    <Link href="/" className="workspace-brand" aria-label="Samora Ledger Tech home">
     <span className="brand-mark" aria-hidden="true">S</span>
     <span className="workspace-brand-copy"><span className="brand-name"> SAMORA LEDGER TECH</span></span>
    </Link>
    <h1 className="header-page-title">{pathname.startsWith("/customer/") ? "Customer Profile" : pathname === "/" ? "Overview" : ({"/transactions":"Transaction Activity","/risk":"Risk & Exposure","/analytics":"Analytics & Trends","/reports":"Management Reports","/governance":"Model Governance","/help":"Help & Guidance","/settings":"Settings","/crm":"Customer Relationship Management","/growth":"Customer Growth Intelligence","/assistant":"AI Employee"} as Record<string,string>)[pathname] || "Executive Workspace"}</h1>
   </div>
   <div id="header-actions-slot" className="header-actions-slot" aria-label="Page actions"/>
   {pathname === "/" && <div className="header-actions" aria-label="Executive overview actions"><button className="btn btn-secondary" type="button" onClick={()=>window.dispatchEvent(new Event("samora:refresh-overview"))}><RefreshCw size={14}/>Refresh</button><button className="btn" type="button" onClick={()=>window.dispatchEvent(new Event("samora:run-analytics"))}><Activity size={14}/>Run analytics</button></div>}
   {!mobileOpen&&<button className="sidebar-open-fab mobile-toggle header-mobile-menu" type="button" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><Menu size={19}/></button>}
  </header>
  {mobileOpen&&<button className="sidebar-scrim" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}/>}
  <aside className={"workspace-sidebar collapsed"+(mobileOpen?" mobile-open":"")+(navDismissed?" nav-dismissed":"")}
   onMouseEnter={()=>setNavDismissed(false)}
   onMouseLeave={()=>setNavDismissed(false)} aria-label="Main navigation">
   <div className="sidebar-topline">
    <span className="sidebar-section-label"></span>
    <button className="sidebar-close mobile-toggle" type="button" onClick={()=>setMobileOpen(false)} aria-label="Close navigation"><X size={18}/></button>
   </div>
   <nav className="sidebar-nav">
    {navItems.map(item=>{const Icon=item.icon;const active=item.href==="/" ? pathname==="/" : pathname===item.href||pathname.startsWith(item.href+"/");return <Link key={item.href} href={item.href} title={item.label} aria-current={active?"page":undefined} className={"sidebar-link"+(active?" active":"")} onClick={event=>{event.currentTarget.blur();setMobileOpen(false);setNavDismissed(true);}}><Icon size={17}/><span>{item.label}</span>{active&&<i className="sidebar-active-mark"/>}</Link>})}
   </nav>
   <div className="sidebar-user" aria-label="Workspace information">
    <span className="sidebar-user-avatar" aria-hidden="true">S</span>
    <span className="sidebar-user-copy"><small>Workspace</small><strong>Demo environment</strong></span>
   </div>
  </aside>
 </>;
}
