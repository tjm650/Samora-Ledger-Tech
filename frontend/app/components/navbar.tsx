"use client";

import Link from "next/link";
import {usePathname} from "next/navigation";
import {useEffect,useRef,useState} from "react";
import {
 Building2,LayoutDashboard,ArrowLeftRight,ShieldAlert,BarChart3,FileText,Scale,
 PanelLeftClose,PanelLeftOpen,Menu,X,HelpCircle,Settings,UserRound,ChevronDown
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
 ]},
 {label:"Workspace",items:[
  {href:"/help",label:"Help",icon:HelpCircle},
  {href:"/settings",label:"Settings",icon:Settings}
 ]}
];

export default function Navbar(){
 const pathname=usePathname();
 const [collapsed,setCollapsed]=useState(false);
 const [mobileOpen,setMobileOpen]=useState(false);
 const [sidebarWidth,setSidebarWidth]=useState(236);
 const resizeStart=useRef<{x:number;width:number}|null>(null);
 useEffect(()=>{
  document.documentElement.style.setProperty("--sidebar-width",`${sidebarWidth}px`);
 },[sidebarWidth]);
 const beginResize=(event:React.PointerEvent<HTMLDivElement>)=>{
  if(collapsed||window.matchMedia("(max-width: 760px)").matches)return;
  event.preventDefault();
  event.currentTarget.setPointerCapture(event.pointerId);
  resizeStart.current={x:event.clientX,width:sidebarWidth};
 };
 const resizeSidebar=(event:React.PointerEvent<HTMLDivElement>)=>{
  if(!resizeStart.current)return;
  setSidebarWidth(Math.min(380,Math.max(200,resizeStart.current.width+event.clientX-resizeStart.current.x)));
 };
 const endResize=()=>{resizeStart.current=null};
 const adjustSidebar=(event:React.KeyboardEvent<HTMLDivElement>)=>{
  if(event.key==="ArrowLeft")setSidebarWidth(width=>Math.max(200,width-10));
  if(event.key==="ArrowRight")setSidebarWidth(width=>Math.min(380,width+10));
 };
 return <>
  <header className="workspace-header">
   <div className="workspace-header-left">
    <Link href="/" className="workspace-brand" aria-label="Samora Ledger Tech home">
     <span className="brand-mark"><Building2 size={19}/></span>
     <span className="workspace-brand-copy"><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">EXECUTIVE INTELLIGENCE</span></span>
    </Link>
   </div>
  </header>
  {!mobileOpen&&<button className="sidebar-open-fab mobile-toggle" type="button" onClick={()=>setMobileOpen(true)} aria-label="Open navigation"><Menu size={19}/></button>}
  {mobileOpen&&<button className="sidebar-scrim" aria-label="Close navigation" onClick={()=>setMobileOpen(false)}/>}
  <aside className={"workspace-sidebar"+(collapsed?" collapsed":"")+(mobileOpen?" mobile-open":"")} style={{width:collapsed?76:sidebarWidth}} aria-label="Main navigation">
   <div className="sidebar-topline">
    <span className="sidebar-section-label">WORKSPACE</span>
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
   {!collapsed&&<div className="sidebar-resize-handle" role="separator" aria-label="Resize navigation sidebar" aria-orientation="vertical" aria-valuemin={220} aria-valuemax={420} aria-valuenow={sidebarWidth} tabIndex={0} onPointerDown={beginResize} onPointerMove={resizeSidebar} onPointerUp={endResize} onPointerCancel={endResize} onKeyDown={adjustSidebar}><span/></div>}
   <div className="sidebar-user" aria-label="Signed-in user">
    <span className="sidebar-user-avatar"><UserRound size={17}/></span>
    <span className="sidebar-user-copy"><small>Signed in as</small><strong>Executive user</strong></span>
    <span className="sidebar-user-status" aria-label="Signed-in session active"/>
    <ChevronDown className="sidebar-user-chevron" size={15}/>
   </div>
  </aside>
 </>;
}
