'use client';

import { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { ChevronDown, Menu, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Category, Brand } from '@/lib/db';

interface HeaderProps {
  categories: Category[];
  brands: Brand[];
}

export default function Header({ categories, brands }: HeaderProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMegaMenuOpen, setIsMegaMenuOpen] = useState(false);

  // Take top 6 brands for featured
  const featuredBrands = brands.slice(0, 6);

  return (
    <header className="sticky top-0 z-50 w-full bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-20">
          
          {/* Logo */}
          <Link href="/" className="flex items-center gap-3">
            <Image src="/ak-logo.png" alt="AK Distributors" width={48} height={48} className="object-contain mix-blend-multiply" />
            <span className="font-heading font-bold text-xl text-brand-dark hidden sm:block">
              AK Distributors
            </span>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-8">
            <div 
              className="relative group h-full"
              onMouseEnter={() => setIsMegaMenuOpen(true)}
              onMouseLeave={() => setIsMegaMenuOpen(false)}
            >
              <button className="flex items-center gap-1 font-semibold text-slate-700 hover:text-brand-primary transition-colors py-7">
                Products <ChevronDown className="w-4 h-4" />
              </button>
              
              {/* Mega Menu Dropdown */}
              <AnimatePresence>
                {isMegaMenuOpen && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    transition={{ duration: 0.2 }}
                    className="absolute top-[80px] left-1/2 -translate-x-1/2 w-[800px] bg-white rounded-xl shadow-2xl border border-slate-100 overflow-hidden flex"
                  >
                    {/* Left: Categories (70%) */}
                    <div className="w-[70%] p-8 bg-white">
                      <h3 className="font-heading font-bold text-lg text-slate-900 mb-6 border-b border-slate-100 pb-2">Categories</h3>
                      <div className="grid grid-cols-2 gap-x-8 gap-y-4">
                        {categories.map((c) => (
                          <Link key={c.id} href={`/products?category=${c.id}`} className="text-sm font-medium text-slate-600 hover:text-brand-primary transition-colors">
                            {c.name}
                          </Link>
                        ))}
                      </div>
                      <div className="mt-8 pt-6 border-t border-slate-100">
                        <Link href="/products" className="text-sm font-semibold text-brand-primary hover:text-brand-primary-hover flex items-center gap-1">
                          View All Products &rarr;
                        </Link>
                      </div>
                    </div>
                    
                    {/* Right: Featured Brands (30%) */}
                    <div className="w-[30%] bg-slate-50 p-8 border-l border-slate-100">
                      <h3 className="font-heading font-bold text-lg text-slate-900 mb-6 border-b border-slate-200 pb-2">Featured Brands</h3>
                      <div className="flex flex-col gap-4">
                        {featuredBrands.map((b) => (
                          <Link key={b.id} href={`/brands?id=${b.id}`} className="text-sm font-medium text-slate-700 hover:text-brand-primary transition-colors">
                            {b.name}
                          </Link>
                        ))}
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            
            <Link href="/brands" className="font-semibold text-slate-700 hover:text-brand-primary transition-colors">Brands</Link>
            <Link href="/catalogs" className="font-semibold text-slate-700 hover:text-brand-primary transition-colors">Catalogs</Link>
            <Link href="/about" className="font-semibold text-slate-700 hover:text-brand-primary transition-colors">About Us</Link>
            <Link href="/contact" className="font-semibold text-slate-700 hover:text-brand-primary transition-colors">Contact Us</Link>
          </nav>

          {/* Action Button & Mobile Toggle */}
          <div className="flex items-center gap-4">
            <button className="hidden md:inline-flex bg-brand-primary hover:bg-brand-primary-hover text-white px-6 py-2.5 rounded-full font-semibold transition-transform hover:scale-95 cursor-pointer">
              Request a Quote
            </button>
            <button 
              className="md:hidden p-2 text-slate-700 cursor-pointer"
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            >
              {isMobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>
      
      {/* Mobile Menu */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="md:hidden bg-white border-t border-slate-100 overflow-hidden"
          >
            <nav className="flex flex-col px-4 py-6 gap-4">
              <Link href="/products" className="text-lg font-semibold text-slate-700">Products</Link>
              <Link href="/brands" className="text-lg font-semibold text-slate-700">Brands</Link>
              <Link href="/catalogs" className="text-lg font-semibold text-slate-700">Catalogs</Link>
              <Link href="/about" className="text-lg font-semibold text-slate-700">About Us</Link>
              <Link href="/contact" className="text-lg font-semibold text-slate-700">Contact Us</Link>
              <button className="bg-brand-primary text-white px-6 py-3 rounded-full font-semibold mt-4 text-center cursor-pointer">
                Request a Quote
              </button>
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
