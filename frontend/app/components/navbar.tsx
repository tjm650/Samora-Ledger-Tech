"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {useEffect,useState} from "react";
import {
 Building2,LayoutDashboard,ArrowLeftRight,ShieldAlert,BarChart3,FileText,Scale,Users,
 PanelLeftClose,PanelLeftOpen,Menu,X,HelpCircle,Settings,UserRound,ChevronDown,RefreshCw,Activity
} from "lucide-react";

const groups=[
 {label:"Overview",items:[
  {href:"/",label:"Overview",icon:LayoutDashboard}
 ]},
 {label:"",items:[
  {href:"/crm",label:"crm",icon:Users}
 ]},
 {label:"Transaction Management",items:[
  {href:"/transactions",label:"Transaction activity",icon:ArrowLeftRight}
 ]},
 {label:"Risk & Controls",items:[
  {href:"/risk",label:"Risks",icon:ShieldAlert},
  {href:"/governance",label:"Model governance",icon:Scale}
 ]},
 {label:"Insights & Reporting",items:[
  {href:"/analytics",label:"Analytics",icon:BarChart3},
  {href:"/reports",label:"Management reports",icon:FileText}
 ]},
 {label:"",items:[
  {href:"/help",label:"Help",icon:HelpCircle},
  {href:"/settings",label:"Settings",icon:Settings}
 ]}
];

export default function Navbar(){
 const pathname=usePathname();
 const [collapsed,setCollapsed]=useState(false);
 const [mobileOpen,setMobileOpen]=useState(false);

 return <>
  <header className="workspace-header">
   <div className="workspace-header-left">
    <Link href="/" className="workspace-brand" aria-label="Samora Ledger Tech home">
     <span className="brand-mark"><Building2 size={19}/></span>
     <span className="workspace-brand-copy"><span className="brand-name">SAMORA LEDGER TECH</span></span>
    </Link>
    <h1 className="header-page-title">{pathname.startsWith("/customer/") ? "Customer Profile" : pathname === "/" ? "Overview" : ({"/transactions":"Transaction Activity","/risk":"Risk & Exposure","/analytics":"Analytics & Trends","/reports":"Management Reports","/governance":"Model Governance","/help":"Help & Guidance","/settings":"Settings","/crm":"Customer Relationship Management"} as Record<string,string>)[pathname] || "Executive Workspace"}</h1>
   </div>
   <div id="header-actions-slot" className="header-actions-slot" aria-label="Page actions"/>
   {pathname === "/" && <div className="header-actions" aria-label="Executive overview actions"><button className="btn btn-secondary" type="button" onClick={()=>window.dispatchEvent(new Event("samora:refresh-overview"))}><RefreshCw size={14}/>Refresh</button><button className="btn" type="button" onClick={()=>window.dispatchEvent(new Event("samora:run-analytics"))}><Activity size={14}/>Run analytics</button></div>}
   {!mobileOpen&&<button className="sidebar-open-fab mobile-toggle header-mobile-menu" type="button" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><Menu size={19}/></button>}
  </header>
  {mobileOpen&&<button className="sidebar-scrim" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}/>}
  <aside className={"workspace-sidebar"+(collapsed?" collapsed":"")+(mobileOpen?" mobile-open":"")} style={{width:collapsed?76:188}} aria-label="Main navigation">
   <div className="sidebar-topline">
    <span className="sidebar-section-label"></span>
    <button className="sidebar-toggle desktop-toggle" type="button" onClick={()=>setCollapsed(v=>!v)} aria-label={collapsed?"Expand navigation":"Collapse navigation"} aria-expanded={!collapsed}>
     {collapsed?<PanelLeftOpen size={18}/>:<PanelLeftClose size={18}/>}
    </button>
    <button className="sidebar-close mobile-toggle" type="button" onClick={()=>setMobileOpen(false)} aria-label="Close navigation"><X size={18}/></button>
   </div>
   <nav className="sidebar-nav">
    {groups.map(group=><section className="sidebar-group" key={group.label}>
     <h2 className="sidebar-group-title">{group.label}</h2>
     {group.items.map(item=>{const Icon=item.icon;const active=item.href==="/" ? pathname==="/" : pathname===item.href||pathname.startsWith(item.href+"/");return <Link key={item.href} href={item.href} title={collapsed?item.label:undefined} aria-current={active?"page":undefined} className={"sidebar-link"+(active?" active":"")} onClick={()=>setMobileOpen(false)}><Icon size={17}/><span>{item.label}</span>{active&&<i className="sidebar-active-mark"/>}</Link>})}
    </section>)}
   </nav>
   <div className="sidebar-user" aria-label="Signed-in user">
    <span className="sidebar-user-avatar"><UserRound size={17}/></span>
    <span className="sidebar-user-copy"><small>Signed in as</small><strong>Executive user</strong></span>
    <span className="sidebar-user-status" aria-label="Signed-in session active"/>
    <ChevronDown className="sidebar-user-chevron" size={15}/>
   </div>
  </aside>
 </>;
}
