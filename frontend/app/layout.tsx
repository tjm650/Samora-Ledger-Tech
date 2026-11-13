import type {Metadata} from "next";
import "./globals.css";
import Navbar from "./components/navbar";
import Footer from "./components/footer";
export const metadata:Metadata={title:{default:"Samora Ledger Tech | Executive Banking Intelligence",template:"%s | Samora Ledger Tech"},description:"Executive banking intelligence for transaction oversight, portfolio-level risk analysis and management reporting."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body><Navbar/><main className="main-shell">{children}</main><Footer/></body></html>}
