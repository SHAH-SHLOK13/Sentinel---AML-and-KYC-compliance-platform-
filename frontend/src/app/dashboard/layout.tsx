"use client";

import { useState } from "react";
import { DashboardSidebar } from "@/components/dashboard/DashboardSidebar";
import { AICopilotTerminal } from "@/components/AICopilotTerminal";
import { motion } from "framer-motion";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

    return (
        <div className="min-h-screen bg-black">
            <DashboardSidebar
                collapsed={sidebarCollapsed}
                onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
            />

            {/* Main content */}
            <motion.main
                animate={{ marginLeft: sidebarCollapsed ? 72 : 260 }}
                transition={{ type: "spring", stiffness: 200, damping: 25 }}
                className="min-h-screen"
            >
                {/* Top bar */}
                <div className="sticky top-0 z-30 border-b border-white/[0.04] bg-black/80 backdrop-blur-xl">
                    <div className="flex items-center justify-between px-8 py-4">
                        <div>
                            <h1 className="text-lg font-semibold text-white">Dashboard</h1>
                            <p className="text-xs text-white/30">
                                Welcome back. Your API is running smoothly.
                            </p>
                        </div>
                        <div className="flex items-center gap-3">
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-sentinel-green/5 border border-sentinel-green/10">
                                <div className="w-2 h-2 rounded-full bg-sentinel-green animate-pulse" />
                                <span className="text-xs text-sentinel-green font-medium">
                                    All Systems Operational
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Page content */}
                <div className="p-8">{children}</div>
            </motion.main>

            {/* AI Copilot */}
            <AICopilotTerminal />
        </div>
    );
}
