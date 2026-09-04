import { getPublicProducts, getBrands } from "@/lib/db";
import { MagicCard } from "@/components/magicui/magic-card";
import Link from "next/link";
import BlurFade from "@/components/magicui/blur-fade";

export default async function Products({
  searchParams,
}: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>
}) {
  const params = await searchParams;
  const brandFilter = typeof params.brand === 'string' ? params.brand : null;
  
  const allProducts = getPublicProducts();
  const products = brandFilter ? allProducts.filter(p => p.brand === brandFilter) : allProducts;
  
  const allBrands = getBrands();

  return (
    <div className="bg-slate-50 min-h-screen pb-24">
      {/* Header */}
      <div className="relative w-full h-[400px] flex flex-col items-center justify-center overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 z-0">
          <div className="absolute inset-0 bg-gradient-to-b from-slate-950/80 via-slate-900/60 to-slate-950/90 z-10" />
          <img
            src="/static/images/catalog_bg.png"
            alt="Products Catalog"
            className="w-full h-full object-cover opacity-60"
          />
        </div>
        <div className="relative z-20 text-center px-4">
          <BlurFade delay={0.1}>
            <h1 className="font-heading text-5xl md:text-6xl font-extrabold mb-4">
              {brandFilter ? brandFilter : "Product Catalog"}
            </h1>
            <p className="text-slate-300 text-lg max-w-2xl mx-auto mb-8">
              {brandFilter ? `Browse our premium selection from ${brandFilter}.` : "Browse our complete selection of premium wholesale products."}
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
        {/* Brand Tabs */}
        <div className="flex overflow-x-auto pb-4 mb-8 gap-3 no-scrollbar">
          <Link href="/products" className={`whitespace-nowrap px-6 py-3 rounded-full font-semibold transition-all border ${!brandFilter ? 'bg-brand-primary text-white border-brand-primary' : 'bg-white text-slate-600 border-slate-200 hover:border-brand-primary hover:text-brand-primary shadow-sm'}`}>
            All Brands
          </Link>
          {allBrands.map(brand => (
            <Link key={brand.id} href={`/products?brand=${encodeURIComponent(brand.name)}`} className={`whitespace-nowrap px-6 py-3 rounded-full font-semibold transition-all border ${brandFilter === brand.name ? 'bg-brand-primary text-white border-brand-primary' : 'bg-white text-slate-600 border-slate-200 hover:border-brand-primary hover:text-brand-primary shadow-sm'}`}>
              {brand.name}
            </Link>
          ))}
        </div>

        {/* Product Grid */}
        {products.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {products.map((product, idx) => (
              <BlurFade key={product.id} delay={0.05 * Math.min(idx, 10)}>
                <MagicCard className="flex flex-col h-full shadow-sm hover:shadow-xl transition-all duration-300 bg-white" gradientColor="#10b98115">
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
        ) : (
          <div className="text-center py-32 bg-white rounded-2xl shadow-sm border border-slate-100">
            <h2 className="font-heading text-2xl font-bold text-slate-900 mb-2">No products available.</h2>
            <p className="text-slate-500">Check back later as we update our catalog.</p>
          </div>
        )}
      </div>
    </div>
  );
}
