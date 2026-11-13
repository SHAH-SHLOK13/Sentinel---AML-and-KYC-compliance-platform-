"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

const ComplianceDashboard = dynamic(
    () => import("@/components/compliance/ComplianceDashboard").then((mod) => mod.ComplianceDashboard),
    { ssr: false }
);

export default function AMLCompliancePage() {
    const router = useRouter();

    const handleLogout = () => {
        router.push("/");
    };

    return (
        <div className="bg-black min-h-screen">
            <ComplianceDashboard onLogout={handleLogout} />
        </div>
    );
}
