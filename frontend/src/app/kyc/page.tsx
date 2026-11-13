"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

const KYCFlow = dynamic(
    () => import("@/components/kyc/KYCFlow").then((mod) => mod.KYCFlow),
    { ssr: false }
);

export default function KYCPage() {
    const router = useRouter();

    // Mock user for demo purpose
    const mockUser = {
        id: "demo_user_123",
        name: "Demo User",
        email: "demo@sentinel.com",
    };

    const handleComplete = () => {
        // Redirect to internal AML user dashboard
        router.push("/aml/user");
    };

    const handleCancel = () => {
        router.push("/");
    };

    return (
        <div className="bg-black min-h-screen">
            <KYCFlow
                user={mockUser}
                onComplete={handleComplete}
                onCancel={handleCancel}
            />
        </div>
    );
}
