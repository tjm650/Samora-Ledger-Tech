import type { Metadata } from "next";
import "./globals.css";
import Navbar from "./components/navbar";
import Footer from "./components/footer";
export const metadata:Metadata={title:"Samora Ledger Tech",description:"Banking transaction analytics and action engine"};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><Navbar/><main style={{maxWidth:1440,margin:"0 auto",padding:"32px 5%"}}>{children}</main><Footer/></body></html>}
