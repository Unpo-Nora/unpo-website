"use client";

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { Play, X } from 'lucide-react';

export default function Hero() {
    const [isVideoOpen, setIsVideoOpen] = useState(false);
    return (
        <section className="relative h-screen min-h-[600px] flex items-center justify-center overflow-hidden">
            {/* Background Image */}
            <div className="absolute inset-0 z-0">
                <Image
                    src="/nora/nora_hero.jpg"
                    alt="NORA Smart Living"
                    fill
                    className="object-cover"
                    priority
                />
                {/* Overlay - Gradient for legibility */}
                <div className="absolute inset-0 bg-black/20"></div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/30"></div>
            </div>

            {/* Content */}
            <div className="relative z-10 text-center px-4 max-w-5xl mx-auto mt-[-5vh]">
                <span className="inline-block py-1 px-3 rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-white text-xs font-semibold tracking-[0.2em] uppercase mb-8 animate-fade-in-up">
                    Nueva Colección 2026
                </span>
                <h1 className="text-6xl md:text-8xl font-serif text-white mb-8 tracking-tight leading-none drop-shadow-2xl">
                    Tecnología diseñada <br /> para ser vista.
                </h1>
                <p className="text-xl md:text-2xl text-slate-100 max-w-2xl mx-auto mb-12 font-light drop-shadow-lg leading-relaxed">
                    Eleva tu espacio con la fusión perfecta de estética premium y funcionalidad inteligente.
                </p>

                <div className="flex flex-col sm:flex-row gap-6 justify-center items-center">
                    <Link href="/nora/shop" className="px-10 py-4 bg-white text-slate-900 text-sm font-bold tracking-widest uppercase hover:bg-slate-200 transition-colors min-w-[200px]">
                        Explorar Colección
                    </Link>
                    <button
                        onClick={() => setIsVideoOpen(true)}
                        className="px-10 py-4 bg-white/5 border border-white/30 text-white text-sm font-bold tracking-widest uppercase hover:bg-white/10 transition-colors min-w-[200px] backdrop-blur-sm flex items-center justify-center gap-2"
                    >
                        <Play size={16} /> Ver Video
                    </button>
                </div>
            </div>

            {/* Video Modal */}
            {isVideoOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/90 p-4 backdrop-blur-md animate-in fade-in duration-300">
                    <button
                        onClick={() => setIsVideoOpen(false)}
                        className="absolute top-8 right-8 text-white/50 hover:text-white transition-colors"
                    >
                        <X size={36} />
                    </button>
                    <div className="relative w-full max-w-6xl aspect-video bg-black rounded-2xl overflow-hidden shadow-2xl border border-white/10">
                        <video
                            src="/nora/videos/NORA_promo.mp4"
                            controls
                            autoPlay
                            className="w-full h-full object-contain"
                        />
                    </div>
                </div>
            )}

            {/* Scroll Indicator */}
            <div className="absolute bottom-10 left-1/2 transform -translate-x-1/2 animate-bounce">
                <svg className="w-6 h-6 text-white opacity-70" fill="none" strokeWidth="1.5" viewBox="0 0 24 24" stroke="currentColor">
                    <path d="M19 14l-7 7m0 0l-7-7m7 7V3"></path>
                </svg>
            </div>
        </section>
    );
}
