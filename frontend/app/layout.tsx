import type { Metadata } from "next";
import "./globals.css";
import Link from "next/link";
export const metadata:Metadata={title:"Samora Ledger Tech",description:"Banking transaction analytics and action engine"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><header style={{background:"#14213d",color:"white",padding:"18px 5%",display:"flex",justifyContent:"space-between",alignItems:"center"}}><strong>◈ SAMORA LEDGER TECH</strong><nav style={{display:"flex",gap:22,fontSize:14}}><Link href="/">Overview</Link><Link href="/crm">Customer CRM</Link></nav></header><main style={{maxWidth:1440,margin:"0 auto",padding:"32px 5%"}}>{children}</main><footer style={{padding:24,textAlign:"center",color:"#64748b",fontSize:12}}>Samora Ledger Tech · Decision support only · Human review required</footer></body></html>}
