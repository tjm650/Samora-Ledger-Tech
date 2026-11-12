import Link from "next/link";
import {Building2,ShieldCheck} from "lucide-react";

export default function Footer(){return <footer className="site-footer"><div className="footer-inner">
 <div className="footer-main">
  <div><Link href="/" className="brand"><span className="brand-mark"><Building2 size={18}/></span><span><span className="brand-name">SAMORA LEDGER TECH</span><span className="brand-sub">BANKING INTELLIGENCE</span></span></Link><p className="footer-brand-copy">A decision-support workspace for customer portfolio intelligence, transaction analytics and relationship management.</p></div>
  <div className="footer-links"><Link href="/">Executive Overview</Link><Link href="/crm">Customer Portfolio</Link><a href="https://github.com/tjm650/Samora-Ledger-Tech" target="_blank" rel="noreferrer">Project Repository</a></div>
 </div>
 <div className="footer-bottom"><span>© {new Date().getFullYear()} Samora Ledger Tech. All rights reserved.</span><span><ShieldCheck size={12} style={{display:"inline",verticalAlign:"-2px",marginRight:5}}/>Decision support only · Human review required · Access governed by your organisation</span></div>
</div></footer>}
