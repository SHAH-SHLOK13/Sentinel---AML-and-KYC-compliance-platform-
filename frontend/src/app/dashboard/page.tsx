"use client";

import { APIKeysSection } from "@/components/dashboard/APIKeysSection";
import { motion } from "framer-motion";
import {
    Activity,
    TrendingUp,
    Users,
    ShieldCheck,
    ArrowUpRight,
    ArrowDownRight,
} from "lucide-react";

// ─── Overview Stats ──────────────────────────────────────────────────
const overviewStats = [
    {
        label: "Total Verifications",
        value: "1,247,893",
        change: "+12.5%",
        trend: "up",
        icon: ShieldCheck,
        color: "text-sentinel-blue",
        bgColor: "bg-sentinel-blue/10",
    },
    {
        label: "Active Users",
        value: "3,421",
        change: "+8.3%",
        trend: "up",
        icon: Users,
        color: "text-sentinel-green",
        bgColor: "bg-sentinel-green/10",
    },
    {
        label: "API Requests (24h)",
        value: "89,742",
        change: "+22.1%",
        trend: "up",
        icon: Activity,
        color: "text-[#ffaa00]",
        bgColor: "bg-[#ffaa00]/10",
    },
    {
        label: "Success Rate",
        value: "99.97%",
        change: "+0.02%",
        trend: "up",
        icon: TrendingUp,
        color: "text-sentinel-green",
        bgColor: "bg-sentinel-green/10",
    },
];

// ─── Recent Activity ─────────────────────────────────────────────────
const recentActivity = [
    {
        action: "KYC Verification",
        status: "verified",
        detail: "US Passport — John D.",
        time: "2 min ago",
    },
    {
        action: "AML Screening",
        status: "clear",
        detail: "OFAC + UN Sanctions",
        time: "5 min ago",
    },
    {
        action: "KYC Verification",
        status: "flagged",
        detail: "UK Driver's License — flagged for review",
        time: "12 min ago",
    },
    {
        action: "PEP Check",
        status: "clear",
        detail: "Politically Exposed Person — clean",
        time: "18 min ago",
    },
    {
        action: "AML Screening",
        status: "flagged",
        detail: "EU Sanctions — partial match (73%)",
        time: "25 min ago",
    },
    {
        action: "KYC Verification",
        status: "verified",
        detail: "Canadian Passport — Sarah L.",
        time: "31 min ago",
    },
];

export default function DashboardPage() {
    return (
        <div className="space-y-8">
            {/* Stats grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                {overviewStats.map((stat, i) => (
                    <motion.div
                        key={stat.label}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.08, duration: 0.4 }}
                        className="p-5 rounded-xl bg-[#0A0A0A] border border-white/[0.06]
                       hover:border-white/[0.1] transition-colors"
                    >
                        <div className="flex items-center justify-between mb-3">
                            <div
                                className={`w-10 h-10 rounded-xl ${stat.bgColor} flex items-center justify-center`}
                            >
                                <stat.icon className={`w-5 h-5 ${stat.color}`} />
                            </div>
                            <div
                                className={`flex items-center gap-1 text-xs font-medium ${stat.trend === "up"
                                        ? "text-sentinel-green"
                                        : "text-sentinel-red"
                                    }`}
                            >
                                {stat.trend === "up" ? (
                                    <ArrowUpRight className="w-3.5 h-3.5" />
                                ) : (
                                    <ArrowDownRight className="w-3.5 h-3.5" />
                                )}
                                {stat.change}
                            </div>
                        </div>
                        <p className="text-2xl font-bold text-white mb-0.5">{stat.value}</p>
                        <p className="text-xs text-white/30">{stat.label}</p>
                    </motion.div>
                ))}
            </div>

            {/* Two-column layout */}
            <div className="grid xl:grid-cols-5 gap-6">
                {/* API Keys — wider */}
                <div className="xl:col-span-3">
                    <APIKeysSection />
                </div>

                {/* Recent Activity — sidebar */}
                <div className="xl:col-span-2">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                        className="rounded-xl bg-[#0A0A0A] border border-white/[0.06] overflow-hidden"
                    >
                        <div className="px-5 py-4 border-b border-white/[0.06]">
                            <h3 className="text-sm font-semibold text-white">
                                Recent Activity
                            </h3>
                            <p className="text-xs text-white/20 mt-0.5">
                                Real-time verification events
                            </p>
                        </div>

                        <div className="divide-y divide-white/[0.04]">
                            {recentActivity.map((event, i) => (
                                <motion.div
                                    key={i}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: 0.4 + i * 0.05 }}
                                    className="flex items-center gap-3 px-5 py-3.5 hover:bg-white/[0.02] transition-colors"
                                >
                                    {/* Status dot */}
                                    <div
                                        className={`w-2 h-2 rounded-full shrink-0 ${event.status === "verified" || event.status === "clear"
                                                ? "bg-sentinel-green"
                                                : "bg-sentinel-red"
                                            }`}
                                    />

                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2">
                                            <span className="text-sm font-medium text-white/70 truncate">
                                                {event.action}
                                            </span>
                                            <span
                                                className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${event.status === "verified" ||
                                                        event.status === "clear"
                                                        ? "bg-sentinel-green/10 text-sentinel-green"
                                                        : "bg-sentinel-red/10 text-sentinel-red"
                                                    }`}
                                            >
                                                {event.status}
                                            </span>
                                        </div>
                                        <p className="text-xs text-white/25 truncate mt-0.5">
                                            {event.detail}
                                        </p>
                                    </div>

                                    <span className="text-[10px] text-white/15 shrink-0 whitespace-nowrap">
                                        {event.time}
                                    </span>
                                </motion.div>
                            ))}
                        </div>
                    </motion.div>
                </div>
            </div>
        </div>
    );
}
