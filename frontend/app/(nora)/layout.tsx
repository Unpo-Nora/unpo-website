import type { Metadata } from "next";

export const metadata: Metadata = {
    title: "NORA — Smart Living",
    description:
        "NORA: Smart Furniture de diseño. Mesas y heladeras inteligentes que fusionan lujo, tecnología y minimalismo para tu living.",
};

export default function NoraLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <>{children}</>;
}
