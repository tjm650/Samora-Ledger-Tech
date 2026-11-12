import Link from "next/link";
import {Building2,ShieldCheck} from "lucide-react";
export default function Footer(){return <footer className="site-footer"><div className="footer-inner">
 <div className="footer-main">
  <div><Link href="/" className="brand"><span className="brand-mark"><Building2 size={18}/></span><span><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">EXECUTIVE INTELLIGENCE</span></span></Link><p className="footer-brand-copy">An executive decision-support environment for banking transaction intelligence, portfolio-level risk oversight and management reporting.</p></div>
  <div className="footer-links"><Link href="/">Executive overview</Link><Link href="/transactions">Transaction activity</Link><Link href="/risk">Risk & exposure</Link><Link href="/analytics">Analytics</Link><Link href="/reports">Management reports</Link><Link href="/governance">Model governance</Link></div>
 </div>
 <div className="footer-bottom"><span>© {new Date().getFullYear()} Samora Ledger Tech. All rights reserved.</span><span><ShieldCheck size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Executive decision support · Human oversight required · Access subject to organisational controls</span></div>
</div></footer>}
