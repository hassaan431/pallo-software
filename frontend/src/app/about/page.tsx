import BlurFade from "@/components/magicui/blur-fade";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function About() {
  return (
    <div className="bg-slate-50 min-h-screen pb-24">
      <div className="relative w-full h-[500px] flex flex-col items-center justify-center overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-900/60 to-slate-950/90 z-10" />
          <img
            src="/static/images/family_business_bg.png"
            alt="About Us"
            className="w-full h-full object-cover opacity-60"
          />
        </div>
        <div className="relative z-20 text-center px-4">
          <BlurFade delay={0.1}>
            <h1 className="font-heading text-5xl md:text-6xl font-extrabold mb-4">About AK Distributors</h1>
            <p className="text-slate-300 text-lg md:text-xl max-w-2xl mx-auto font-light">
              Your trusted partner in premium wholesale distribution.
            </p>
          </BlurFade>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <BlurFade delay={0.2}>
          <div className="prose prose-lg prose-slate max-w-none">
            <h2 className="font-heading text-4xl font-bold text-slate-900 mb-6">Our Story</h2>
            <p className="text-slate-700 leading-relaxed mb-12">
              As a proud family-owned business, AK Distributors has spent years building a reputation for excellence in the wholesale distribution sector. We understand the value of strong relationships, reliable supply chains, high-quality products, and transparent communication. We are incredibly proud to be the exclusive distributors of <strong>Bake Parlor</strong> and <strong>Youngs Food</strong> in California, bridging the gap between these premium manufacturers and growing businesses, ensuring you always have the inventory you need to succeed.
            </p>
            
            <h2 className="font-heading text-4xl font-bold text-slate-900 mb-6">Why Choose Us?</h2>
            <p className="text-slate-700 leading-relaxed mb-6">
              We believe in building long-term partnerships rather than just processing transactions. When you partner with AK Distributors, you benefit from:
            </p>
            
            <ul className="space-y-4 mb-16">
              <li className="flex gap-3 text-slate-700">
                <span className="text-brand-primary font-bold">✓</span>
                <span><strong>Exclusive Brands:</strong> As the sole distributors of Bake Parlor and Youngs Food in California, we provide access to products you won't find anywhere else.</span>
              </li>
              <li className="flex gap-3 text-slate-700">
                <span className="text-brand-primary font-bold">✓</span>
                <span><strong>Family-Owned Values:</strong> We treat our partners like family, prioritizing long-term trust over short-term transactions.</span>
              </li>
              <li className="flex gap-3 text-slate-700">
                <span className="text-brand-primary font-bold">✓</span>
                <span><strong>Reliability:</strong> Consistent and timely deliveries so your business never misses a beat.</span>
              </li>
              <li className="flex gap-3 text-slate-700">
                <span className="text-brand-primary font-bold">✓</span>
                <span><strong>Dedicated Support:</strong> Our team is always here to assist with your custom needs and large-scale orders.</span>
              </li>
            </ul>
          </div>

          <div className="bg-white rounded-2xl p-10 md:p-16 text-center border border-slate-100 shadow-xl shadow-slate-200/50">
            <h3 className="font-heading text-3xl font-bold text-slate-900 mb-4">Get in Touch</h3>
            <p className="text-slate-500 mb-8 max-w-md mx-auto">Ready to place an order or looking for custom solutions? Our team is standing by.</p>
            
            <div className="flex flex-col md:flex-row items-center justify-center gap-6 mb-10 text-slate-700 font-medium">
              <div><span className="text-slate-400 block text-sm">Email</span> akdistributorsusa@gmail.com</div>
              <div className="hidden md:block w-px h-10 bg-slate-200"></div>
              <div><span className="text-slate-400 block text-sm">Phone</span> (916) 354-5678</div>
              <div className="hidden md:block w-px h-10 bg-slate-200"></div>
              <div><span className="text-slate-400 block text-sm">Address</span> Sacramento CA, USA</div>
            </div>

            <Link href="/products" className="inline-flex bg-brand-primary hover:bg-brand-primary-hover text-white px-8 py-4 rounded-full font-semibold transition-transform hover:scale-95 items-center justify-center gap-2 shadow-[0_0_20px_rgba(16,185,129,0.3)]">
              Browse Our Catalog <ArrowRight className="w-5 h-5" />
            </Link>
          </div>
        </BlurFade>
      </div>
    </div>
  );
}
