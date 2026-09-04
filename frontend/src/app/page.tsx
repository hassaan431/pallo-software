import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Download, Truck, ShieldCheck, Factory } from "lucide-react";
import { getBrands, getPublicProducts } from "@/lib/db";

import BlurFade from "@/components/magicui/blur-fade";
import { DotPattern } from "@/components/magicui/dot-pattern";
import { Marquee } from "@/components/magicui/marquee";
import { BentoGrid, BentoCard } from "@/components/magicui/bento-grid";
import { MagicCard } from "@/components/magicui/magic-card";

export default function Home() {
  const brands = getBrands();
  const allProducts = getPublicProducts();
  const products = [...allProducts].sort(() => 0.5 - Math.random()).slice(0, 8); // Random preview of products

  const features = [
    {
      name: "Fast Sacramento Dispatch",
      description: "Optimized logistics ensuring next-day delivery across Northern California.",
      Icon: Truck,
      background: (
        <div className="absolute inset-0 bg-slate-100 dark:bg-slate-900 overflow-hidden opacity-50">
           <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-emerald-500/10 via-transparent to-transparent" />
        </div>
      ),
      className: "lg:col-span-1",
    },
    {
      name: "Verified Quality",
      description: "Rigorous quality control for every batch before it reaches your shelves.",
      Icon: ShieldCheck,
      background: (
        <div className="absolute inset-0 bg-slate-100 dark:bg-slate-900 opacity-50 overflow-hidden">
           <div className="absolute -top-10 -right-10 w-64 h-64 bg-slate-300 rounded-full mix-blend-multiply filter blur-3xl opacity-70" />
        </div>
      ),
      className: "lg:col-span-1",
    },
    {
      name: "Direct Sourcing",
      description: "Exclusive partnerships with top manufacturers to bring you unbeatable margins.",
      Icon: Factory,
      background: (
        <div className="absolute inset-0 bg-slate-100 dark:bg-slate-900 opacity-50 overflow-hidden">
          <div className="absolute bottom-0 left-0 right-0 h-1/2 bg-gradient-to-t from-slate-200 to-transparent" />
        </div>
      ),
      className: "lg:col-span-1",
    },
  ];

  return (
    <>
      {/* Cinematic Hero Section */}
      <section className="relative w-full h-[700px] flex items-center justify-center overflow-hidden bg-slate-950">
        <DotPattern className="opacity-20" cx={2} cy={2} cr={2} />
        
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-900/60 to-slate-950/90 z-10" />
          <Image
            src="/static/images/hero_bg.png"
            alt="Warehouse"
            fill
            className="object-cover opacity-60"
            priority
          />
        </div>

        <div className="relative z-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-white">
          <BlurFade delay={0.1}>
            <h1 className="font-heading text-4xl sm:text-6xl lg:text-8xl font-extrabold tracking-tight mb-6">
              Wholesale Distribution, <br/><span className="text-brand-primary">Refined.</span>
            </h1>
          </BlurFade>
          
          <BlurFade delay={0.2}>
            <p className="text-base sm:text-xl md:text-2xl text-slate-300 max-w-3xl mx-auto mb-8 sm:mb-10 leading-relaxed font-light">
              Connecting Desi Brands & Fresh Ingredients to Supermarkets, Grocers, and Foodservice Across California & Beyond.
            </p>
          </BlurFade>
          
          <BlurFade delay={0.3}>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link href="/products" className="w-full sm:w-auto bg-brand-primary hover:bg-brand-primary-hover text-white px-8 py-4 rounded-full font-semibold transition-transform hover:scale-95 flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)]">
                Explore Product Catalog <ArrowRight className="w-5 h-5" />
              </Link>
              <Link href="/catalogs" className="w-full sm:w-auto bg-white/10 hover:bg-white/20 backdrop-blur-sm border border-white/20 text-white px-8 py-4 rounded-full font-semibold transition-colors flex items-center justify-center gap-2">
                Download PDF Catalog <Download className="w-5 h-5" />
              </Link>
            </div>
          </BlurFade>
        </div>
      </section>

      {/* Infinite Marquee Brands Section */}
      <section className="py-12 sm:py-20 bg-white border-b border-slate-100 overflow-hidden">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mb-6 sm:mb-10">
          <h2 className="text-center font-heading font-bold text-xl sm:text-2xl text-slate-400 uppercase tracking-widest">Our Featured Partners</h2>
        </div>
        
        <div className="relative flex w-full flex-col items-center justify-center overflow-hidden bg-white">
          <Marquee pauseOnHover className="[--duration:30s]">
            {brands.map((brand) => (
              <div key={brand.id} className="mx-6 sm:mx-8 flex items-center justify-center h-16 sm:h-20 transition-all duration-300 cursor-pointer">
                {brand.logo_filename ? (
                  <img 
                    src={`/static/logos/brands/${brand.logo_filename}`} 
                    alt={brand.name} 
                    className="max-h-12 sm:max-h-16 object-contain"
                  />
                ) : (
                  <span className="font-bold text-2xl sm:text-3xl font-heading text-slate-800">
                    {brand.name}
                  </span>
                )}
              </div>
            ))}
          </Marquee>
          <div className="pointer-events-none absolute inset-y-0 left-0 w-16 sm:w-1/3 bg-gradient-to-r from-white"></div>
          <div className="pointer-events-none absolute inset-y-0 right-0 w-16 sm:w-1/3 bg-gradient-to-l from-white"></div>
        </div>
      </section>

      {/* Bento Grid Features */}
      <section className="py-16 sm:py-24 bg-slate-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12 sm:mb-16">
            <BlurFade delay={0.1}>
              <h2 className="font-heading font-bold text-3xl sm:text-4xl text-slate-900 mb-4">Why Choose AK Distributors?</h2>
              <p className="text-slate-600 text-base sm:text-lg max-w-2xl mx-auto">We combine decades of experience with modern logistics to ensure your shelves are always stocked with the highest quality goods.</p>
            </BlurFade>
          </div>
          
          <BlurFade delay={0.15}>
            <BentoGrid>
              {features.map((feature) => (
                <BentoCard key={feature.name} {...feature} />
              ))}
            </BentoGrid>
          </BlurFade>
        </div>
      </section>

      {/* Latest Arrivals with Magic Cards */}
      <section className="py-16 sm:py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-8 sm:mb-12 gap-4">
            <BlurFade delay={0.1}>
              <h2 className="font-heading font-bold text-3xl sm:text-4xl text-slate-900 mb-2 sm:mb-4">Latest Arrivals</h2>
              <p className="text-slate-600 text-base sm:text-lg">Discover our newest wholesale offerings ready for dispatch.</p>
            </BlurFade>
            <Link href="/products" className="hidden sm:flex text-brand-primary hover:text-brand-primary-hover font-semibold items-center gap-2">
              View Catalog <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 sm:gap-8">
            {products.map((product, idx) => (
              <BlurFade key={product.id} delay={0.05 * Math.min(idx, 8)}>
                <MagicCard
                  className="flex flex-col h-full shadow-sm hover:shadow-xl transition-all duration-300 bg-white"
                  gradientColor="#10b98115"
                >
                  <div className="relative aspect-square bg-slate-50/80 p-6 flex items-center justify-center border-b border-slate-100 rounded-t-xl z-20">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} className="object-contain max-h-full mix-blend-multiply group-hover:scale-105 transition-transform duration-500" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center p-4 text-center">
                        <span className="font-heading font-extrabold text-lg sm:text-xl text-slate-800 line-clamp-3 leading-snug">
                          {product.name}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="p-6 flex flex-col flex-1 bg-white rounded-b-xl z-20 relative">
                    <span className="text-xs font-bold text-brand-primary uppercase tracking-wider mb-2">{product.brand || 'Unbranded'}</span>
                    <h3 className="font-heading font-bold text-lg text-slate-900 mb-2 line-clamp-2">{product.name}</h3>
                    <div className="text-sm text-slate-500 mb-6 flex-1 space-y-1">
                      <p><span className="font-medium text-slate-700">Category:</span> {product.category_name}</p>
                    </div>
                  </div>
                </MagicCard>
              </BlurFade>
            ))}
          </div>
          
          <div className="mt-12 text-center sm:hidden">
            <Link href="/products" className="inline-flex text-brand-primary hover:text-brand-primary-hover font-semibold items-center gap-2">
              View All Products <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>
    </>
  );
}
