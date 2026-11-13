"use client";

import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";

const UserDashboard = dynamic(
    () => import("@/components/user/UserDashboard").then((mod) => mod.UserDashboard),
    { ssr: false }
);

export default function AMLUserPage() {
    const router = useRouter();

    // Mock user data for demo
    const mockUser = {
        id: "demo_user_123",
        name: "Demo User",
        email: "demo@sentinel.com",
        balance: 50000,
        riskScore: 15,
    };

    // Mock bank accounts for demo
    const mockBankAccounts = [
        {
            id: "acc_1",
            accountNumber: "1234567890",
            accountHolderName: "Demo User",
            ifscCode: "HDFC0001234",
            bankName: "HDFC Bank",
            accountType: "savings" as const,
            isPrimary: true,
        },
    ];

    const handleLogout = () => {
        router.push("/");
    };

    return (
        <div className="bg-black min-h-screen">
            <UserDashboard
                user={mockUser}
                bankAccounts={mockBankAccounts}
                onLogout={handleLogout}
            />
        </div>
    );
}
