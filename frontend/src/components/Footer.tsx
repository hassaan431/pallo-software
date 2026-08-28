import Link from 'next/link';
import { Mail, MapPin, Phone } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="bg-brand-darker text-slate-300 py-16 border-t border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12">
          
          {/* Column 1: Company Bio */}
          <div>
            <h3 className="font-heading font-bold text-white text-xl mb-4">AK Distributors</h3>
            <p className="text-sm leading-relaxed mb-6">
              Your trusted partner in premium wholesale food distribution. Connecting global brands and fresh ingredients to supermarkets, grocers, and foodservice across California and beyond.
            </p>
            <p className="text-xs text-slate-500">
              Licensed Wholesale Distributor
            </p>
          </div>

          {/* Column 2: Quick Links */}
          <div>
            <h4 className="font-heading font-semibold text-white text-lg mb-4">Quick Links</h4>
            <ul className="space-y-3 text-sm">
              <li><Link href="/products" className="hover:text-brand-primary transition-colors">Our Products</Link></li>
              <li><Link href="/brands" className="hover:text-brand-primary transition-colors">Featured Brands</Link></li>
              <li><Link href="/about" className="hover:text-brand-primary transition-colors">About Us</Link></li>
              <li><Link href="/contact" className="hover:text-brand-primary transition-colors">Contact Us</Link></li>
              <li><Link href="/faq" className="hover:text-brand-primary transition-colors">FAQ & Support</Link></li>
            </ul>
          </div>

          {/* Column 3: Resources */}
          <div>
            <h4 className="font-heading font-semibold text-white text-lg mb-4">Resources</h4>
            <ul className="space-y-3 text-sm">
              <li><Link href="/catalogs" className="hover:text-brand-primary transition-colors">Download PDF Catalog</Link></li>
              <li><Link href="/terms" className="hover:text-brand-primary transition-colors">Terms of Trade</Link></li>
              <li><Link href="/privacy" className="hover:text-brand-primary transition-colors">Privacy Policy</Link></li>
              <li><Link href="/shipping" className="hover:text-brand-primary transition-colors">Shipping & Returns</Link></li>
            </ul>
          </div>

          {/* Column 4: Contact Info */}
          <div>
            <h4 className="font-heading font-semibold text-white text-lg mb-4">Contact Us</h4>
            <ul className="space-y-4 text-sm">
              <li className="flex items-start gap-3">
                <MapPin className="w-5 h-5 text-brand-primary shrink-0 mt-0.5" />
                <span>AK DISTRIBUTORS LLC,<br />Sacramento, California 95838,<br />U.S.A</span>
              </li>
              <li className="flex items-center gap-3">
                <Phone className="w-5 h-5 text-brand-primary shrink-0" />
                <a href="tel:+19163545678" className="hover:text-brand-primary transition-colors">+1 (916) 354-5678</a>
              </li>
              <li className="flex items-center gap-3">
                <Mail className="w-5 h-5 text-brand-primary shrink-0" />
                <a href="mailto:akdistributorsusa@gmail.com" className="hover:text-brand-primary transition-colors">akdistributorsusa@gmail.com</a>
              </li>
            </ul>
          </div>
          
        </div>
        
        {/* Bottom Bar */}
        <div className="mt-16 pt-8 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-slate-500">
          <p>&copy; {new Date().getFullYear()} AK Distributors LLC. All rights reserved.</p>
          <a href="http://127.0.0.1:5000/login" className="hover:text-brand-primary transition-colors">
            Client Portal Login
          </a>
        </div>
      </div>
    </footer>
  );
}
