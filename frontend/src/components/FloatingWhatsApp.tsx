'use client';

import { useState } from 'react';
import { MessageCircle, FileText, X, Send } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

export default function FloatingWhatsApp() {
  const [isOpen, setIsOpen] = useState(false);
  const [isQuoteOpen, setIsQuoteOpen] = useState(false);

  const handleWhatsApp = () => {
    const text = encodeURIComponent("Hello AK Distributors, I'd like to inquire about wholesale pricing.");
    window.open(`https://wa.me/19163545678?text=${text}`, '_blank');
    setIsOpen(false);
  };

  return (
    <>
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end">
        
        {/* Expanded Options */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 20, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 20, scale: 0.9 }}
              className="flex flex-col gap-3 mb-4 items-end"
            >
              <button
                onClick={() => { setIsQuoteOpen(true); setIsOpen(false); }}
                className="flex items-center gap-3 bg-white text-slate-800 px-4 py-3 rounded-full shadow-lg border border-slate-100 hover:bg-slate-50 transition-colors font-medium whitespace-nowrap"
              >
                Request a Quick Quote
                <div className="bg-brand-primary p-2 rounded-full text-white">
                  <FileText className="w-4 h-4" />
                </div>
              </button>
              
              <button
                onClick={handleWhatsApp}
                className="flex items-center gap-3 bg-white text-slate-800 px-4 py-3 rounded-full shadow-lg border border-slate-100 hover:bg-slate-50 transition-colors font-medium whitespace-nowrap"
              >
                Chat on WhatsApp
                <div className="bg-[#25D366] p-2 rounded-full text-white">
                  <MessageCircle className="w-4 h-4" />
                </div>
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Main Floating Button */}
        <button
          onClick={() => setIsOpen(!isOpen)}
          className={`relative flex items-center justify-center w-16 h-16 rounded-full shadow-xl transition-transform hover:scale-105 ${
            isOpen ? 'bg-slate-800' : 'bg-brand-primary'
          } text-white`}
        >
          {/* Pulse Effect */}
          {!isOpen && (
            <span className="absolute inset-0 w-full h-full rounded-full bg-brand-primary opacity-50 animate-ping"></span>
          )}
          {isOpen ? <X className="w-8 h-8 relative z-10" /> : <MessageCircle className="w-8 h-8 relative z-10" />}
        </button>
      </div>

      {/* Quick Quote Modal */}
      <AnimatePresence>
        {isQuoteOpen && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden"
            >
              <div className="flex justify-between items-center p-6 border-b border-slate-100 bg-slate-50">
                <h3 className="font-heading font-bold text-xl text-slate-900">Request a Quick Quote</h3>
                <button onClick={() => setIsQuoteOpen(false)} className="text-slate-400 hover:text-slate-600">
                  <X className="w-5 h-5" />
                </button>
              </div>
              
              <form className="p-6 flex flex-col gap-5" onSubmit={(e) => { e.preventDefault(); setIsQuoteOpen(false); alert("Quote request sent!"); }}>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Full Name</label>
                  <input required type="text" className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-primary focus:border-brand-primary outline-none" placeholder="John Doe" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Business Phone</label>
                  <input required type="tel" className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-primary focus:border-brand-primary outline-none" placeholder="(916) 555-0123" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Products Needed</label>
                  <textarea required rows={4} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-primary focus:border-brand-primary outline-none resize-none" placeholder="E.g., 50 cases of Bake Parlor Spaghetti..." />
                </div>
                
                <button type="submit" className="w-full bg-brand-primary hover:bg-brand-primary-hover text-white font-semibold py-3 rounded-lg flex justify-center items-center gap-2 transition-colors mt-2">
                  Send Request <Send className="w-4 h-4" />
                </button>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  );
}
