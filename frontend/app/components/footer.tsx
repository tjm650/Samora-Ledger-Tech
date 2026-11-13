import Link from "next/link";
import {Building2} from "lucide-react";

export default function Footer(){
 return <footer className="site-footer">
  <div className="footer-inner">
   <div className="footer-main">
    <div className="footer-brand-block">
     <Link href="/" className="brand" aria-label="Samora Ledger Tech home">
      <span className="brand-mark"><Building2 size={18}/></span>
      <span><span className="brand-name">SAMORA LEDGER TECH</span></span>
     </Link>
    </div>
    <nav className="footer-links" aria-label="Platform navigation">
     <span className="footer-links-heading">Platform</span>
     <Link href="/">Overview</Link>     <Link href="/crm">Customer management</Link>
     <Link href="/transactions">Transactions</Link>
     <Link href="/risk">Risk &amp; exposure</Link>
     <Link href="/reports">Management reports</Link>
    </nav>
   </div>
   <div className="footer-bottom">
    <span>© {new Date().getFullYear()} Samora Ledger Tech. All rights reserved.</span>
   </div>
  </div>
 </footer>;
}
