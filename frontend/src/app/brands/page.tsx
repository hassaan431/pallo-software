import { getBrands } from "@/lib/db";
import BlurFade from "@/components/magicui/blur-fade";
import Link from "next/link";
import { MagicCard } from "@/components/magicui/magic-card";

export default function Brands() {
  const brands = getBrands();

  return (
    <div className="bg-slate-50 min-h-screen pb-24">
      {/* Header */}
      <div className="relative w-full h-[400px] flex flex-col items-center justify-center overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-900/60 to-slate-950/90 z-10" />
          <img
            src="/static/images/brands_bg.png"
            alt="Our Brands"
            className="w-full h-full object-cover opacity-60"
          />
        </div>
        <div className="relative z-20 text-center px-4">
          <BlurFade delay={0.1}>
            <h1 className="font-heading text-5xl md:text-6xl font-extrabold mb-4">Our Brands</h1>
            <p className="text-slate-300 text-lg max-w-2xl mx-auto mb-8">
              We partner with top-tier brands to bring you the best products.
            </p>
            <div className="flex justify-center">
              <a href="/catalogs" className="inline-flex bg-white/10 hover:bg-white/20 backdrop-blur-sm border border-white/20 text-white px-6 py-3 rounded-full font-semibold transition-colors items-center justify-center gap-2">
                Download PDF Catalog
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </a>
            </div>
          </BlurFade>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 -mt-8 relative z-30">
        {brands.length > 0 ? (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {brands.map((brand, idx) => (
              <BlurFade key={brand.id} delay={0.05 * Math.min(idx, 15)}>
                <Link href={`/products?brand=${encodeURIComponent(brand.name)}`} className="group">
                  <MagicCard className="flex flex-col items-center justify-center h-48 bg-white shadow-sm hover:shadow-xl transition-all duration-300 cursor-pointer" gradientColor="#10b98115">
                    <div className="relative z-20 p-6 flex items-center justify-center h-full w-full">
                      {brand.logo_filename ? (
                        <img 
                          src={`/static/logos/brands/${brand.logo_filename}`} 
                          alt={brand.name} 
                          className="max-h-24 max-w-[80%] object-contain group-hover:scale-105 transition-transform duration-500" 
                        />
                      ) : (
                        <span className="font-heading font-bold text-xl text-slate-800 text-center group-hover:scale-105 transition-transform duration-500">{brand.name}</span>
                      )}
                    </div>
                  </MagicCard>
                </Link>
              </BlurFade>
            ))}
          </div>
        ) : (
          <div className="text-center py-32 bg-white rounded-2xl shadow-sm border border-slate-100">
            <h2 className="font-heading text-2xl font-bold text-slate-900 mb-2">No brands available.</h2>
            <p className="text-slate-500">Check back later as we update our catalog.</p>
          </div>
        )}
      </div>
    </div>
  );
}
