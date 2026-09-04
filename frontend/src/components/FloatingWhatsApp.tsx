'use client';

import { Phone } from 'lucide-react';

export default function FloatingWhatsApp() {
  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
      <a
        href="tel:+19163545678"
        className="relative flex items-center justify-center w-16 h-16 rounded-full shadow-xl transition-transform hover:scale-105 bg-brand-primary text-white"
        title="Call Us"
      >
        <span className="absolute inset-0 w-full h-full rounded-full bg-brand-primary opacity-50 animate-ping"></span>
        <Phone className="w-8 h-8 relative z-10" />
      </a>
    </div>
  );
}
