"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const NAV = [
  { label: "Dashboard", href: "/dashboard", icon: "◆" },
  { label: "Workspace", href: "/dashboard/workspace", icon: "▸", roles: ["admin", "analyst"] },
  { label: "Sessions", href: "/dashboard/sessions", icon: "▦", roles: ["admin", "analyst"] },
  { label: "Compare", href: "/dashboard/compare", icon: "⇌", roles: ["admin", "analyst"] },
  { label: "Downloads", href: "/dashboard/downloads", icon: "↓" },
  { label: "Admin", href: "/dashboard/admin", icon: "⚙", roles: ["admin"] },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user, logout } = useAuth();

  const visibleNav = NAV.filter((n) => {
    if (!n.roles) return true;
    return user && n.roles.includes(user.role);
  });

  return (
    <>
      {/* Mobile overlay */}
      <button
        className="md:hidden fixed top-4 left-4 z-50 bg-[#0f172a] border border-[#1e293b] rounded p-2 text-gray-400"
        onClick={() => setCollapsed(!collapsed)}
        aria-label="Toggle sidebar"
      >
        <svg width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
          {collapsed ? <path d="M6 6l8 8M6 14L14 6" /> : <path d="M4 6h12M4 10h12M4 14h12" />}
        </svg>
      </button>

      <aside
        className={`fixed top-0 left-0 h-screen bg-[#0a0f1c] border-r border-[#1e293b] flex flex-col z-40 transition-all ${
          collapsed ? "-translate-x-full md:translate-x-0 md:w-16" : "w-56"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center gap-2 px-4 py-5 border-b border-[#1e293b]">
          {!collapsed && (
            <Link href="/dashboard" className="text-lg font-bold tracking-wide text-white">
              STRATEGOS
            </Link>
          )}
          <button
            className="hidden md:block ml-auto text-gray-500 hover:text-gray-300"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? "»" : "«"}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-4 space-y-0.5 overflow-y-auto">
          {visibleNav.map((n) => {
            const active = pathname === n.href || pathname.startsWith(n.href + "/");
            return (
              <Link
                key={n.href}
                href={n.href}
                className={`flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  active
                    ? "text-amber-400 bg-amber-400/5 border-r-2 border-amber-400"
                    : "text-gray-400 hover:text-white hover:bg-white/[0.03]"
                }`}
              >
                <span className="w-5 text-center text-xs">{n.icon}</span>
                {!collapsed && n.label}
              </Link>
            );
          })}
        </nav>

        {/* User */}
        {user && (
          <div className="border-t border-[#1e293b] p-4">
            {!collapsed && (
              <div className="mb-2">
                <p className="text-xs text-white font-medium truncate">{user.name}</p>
                <p className="text-[10px] text-gray-500 uppercase">{user.role}</p>
              </div>
            )}
            <button
              onClick={logout}
              className="text-xs text-gray-500 hover:text-red-400 transition-colors"
            >
              {collapsed ? "×" : "Logout"}
            </button>
          </div>
        )}
      </aside>
    </>
  );
}
