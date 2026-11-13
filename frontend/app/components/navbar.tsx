"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const links = [
  { href: "/", label: "Executive Overview" },
  { href: "/crm", label: "Customer CRM" },
];

export default function Navbar() {
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header
      style={{
        position: "relative",
        zIndex: 20,
        width: "100%",
        background: "#14213d",
        color: "#ffffff",
        borderBottom: "3px solid #0f766e",
        boxShadow: "0 3px 14px rgba(15, 23, 42, 0.14)",
      }}
    >
      <div
        style={{
          maxWidth: 1440,
          minHeight: 76,
          margin: "0 auto",
          padding: "14px 5%",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 24,
          flexWrap: "wrap",
        }}
      >
        <Link
          href="/"
          aria-label="Samora Ledger Tech home"
          onClick={() => setMenuOpen(false)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 11,
            color: "#ffffff",
            fontWeight: 800,
            letterSpacing: 1.1,
            fontSize: 16,
            whiteSpace: "nowrap",
          }}
        >
          <span aria-hidden="true" style={{ color: "#5eead4", fontSize: 25 }}>◈</span>
          <span>SAMORA LEDGER TECH</span>
        </Link>

        <nav
          aria-label="Main navigation"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            gap: 8,
            flexWrap: "wrap",
          }}
        >
          {links.map((link) => {
            const active =
              link.href === "/" ? pathname === "/" : pathname === link.href || pathname.startsWith(link.href + "/");
            return (
              <Link
                key={link.href}
                href={link.href}
                aria-current={active ? "page" : undefined}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  minHeight: 42,
                  padding: "10px 16px",
                  borderRadius: 8,
                  color: active ? "#ffffff" : "#dbe5f3",
                  background: active ? "#0f766e" : "transparent",
                  border: active ? "1px solid #2dd4bf" : "1px solid transparent",
                  fontSize: 14,
                  fontWeight: active ? 700 : 600,
                  whiteSpace: "nowrap",
                  transition: "background 150ms ease, border-color 150ms ease",
                }}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
