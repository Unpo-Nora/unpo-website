"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

export default function VisitorTracker() {
    const hasTracked = useRef(false);
    const pathname = usePathname();

    useEffect(() => {
        // Prevent tracking multiple times in development strictly mode
        if (hasTracked.current) return;

        // NORA public surfaces must NOT feed UNPO analytics (Etapa 3.2-B).
        // NORA has no dedicated analytics yet; revisit when backend supports brand.
        if (pathname?.startsWith("/nora")) return;

        const trackVisit = async () => {
            try {
                let visitorId = localStorage.getItem("unpo_visitor_id");
                
                if (!visitorId) {
                    // Generate a simple unique ID
                    visitorId = crypto.randomUUID 
                        ? crypto.randomUUID() 
                        : Math.random().toString(36).substring(2, 15);
                        
                    localStorage.setItem("unpo_visitor_id", visitorId);
                    
                    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
                    
                    await fetch(`${apiUrl}/analytics/visit`, {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json"
                        },
                        body: JSON.stringify({ visitor_id: visitorId })
                    });
                }
            } catch (err) {
                console.error("Failed to track visit", err);
            }
        };

        trackVisit();
        hasTracked.current = true;
    }, []);

    return null; // Invisible component
}
