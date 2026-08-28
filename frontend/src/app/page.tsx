import Image from "next/image";
import Link from "next/link";
import { ArrowRight, Download, Truck, ShieldCheck, Factory } from "lucide-react";
import { getBrands, getCategories, getPublicProducts } from "@/lib/db";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import FloatingWhatsApp from "@/components/FloatingWhatsApp";

export default function Home() {
  const brands = getBrands();
  const categories = getCategories();
  const products = getPublicProducts().slice(0, 8); // Preview of latest products

  return (
    <div className="min-h-screen flex flex-col font-sans">
      <Header categories={categories} brands={brands} />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="relative w-full h-[600px] flex items-center justify-center overflow-hidden">
          {/* Background Image with Overlay */}
          <div className="absolute inset-0 z-0">
            <Image
              src="/static/images/hero_bg.png"
              alt="Warehouse"
              fill
              className="object-cover"
              priority
            />
            <div className="absolute inset-0 bg-slate-900/70 mix-blend-multiply" />
            <div className="absolute inset-0 bg-gradient-to-t from-slate-900 via-transparent to-transparent" />
          </div>

          <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center text-white mt-12">
            <h1 className="font-heading text-5xl md:text-6xl lg:text-7xl font-extrabold tracking-tight mb-6">
              Premium Wholesale Food <span className="text-brand-primary">Distribution</span>
            </h1>
            <p className="text-lg md:text-xl text-slate-200 max-w-3xl mx-auto mb-10 leading-relaxed">
              Connecting Global Brands & Fresh Ingredients to Supermarkets, Grocers, and Foodservice Across California & Beyond.
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
              <Link href="/products" className="w-full sm:w-auto bg-brand-primary hover:bg-brand-primary-hover text-white px-8 py-4 rounded-full font-semibold transition-transform hover:scale-95 flex items-center justify-center gap-2">
                Explore Product Catalog <ArrowRight className="w-5 h-5" />
              </Link>
              <Link href="/catalogs" className="w-full sm:w-auto bg-white/10 hover:bg-white/20 backdrop-blur-sm border border-white/20 text-white px-8 py-4 rounded-full font-semibold transition-colors flex items-center justify-center gap-2">
                Download PDF Catalog <Download className="w-5 h-5" />
              </Link>
            </div>

            {/* Trust Badges */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto pt-8 border-t border-white/20">
              <div className="flex items-center justify-center gap-3">
                <Truck className="w-6 h-6 text-brand-primary" />
                <span className="font-medium text-slate-200">Fast Sacramento Dispatch</span>
              </div>
              <div className="flex items-center justify-center gap-3">
                <ShieldCheck className="w-6 h-6 text-brand-primary" />
                <span className="font-medium text-slate-200">Verified Quality</span>
              </div>
              <div className="flex items-center justify-center gap-3">
                <Factory className="w-6 h-6 text-brand-primary" />
                <span className="font-medium text-slate-200">Direct Manufacturer Sourcing</span>
              </div>
            </div>
          </div>
        </section>

        {/* Valued Brands Ecosystem */}
        <section className="py-16 bg-white border-b border-slate-100">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <h2 className="text-center font-heading font-bold text-2xl text-slate-400 mb-10 uppercase tracking-widest">Our Featured Partners</h2>
            <div className="flex flex-wrap justify-center gap-12 items-center opacity-80">
              {brands.slice(0, 8).map((brand) => (
                <div key={brand.id} className="relative group flex items-center justify-center h-20 px-6 py-2 grayscale opacity-70 hover:grayscale-0 hover:opacity-100 transition-all duration-300">
                  <span className="font-bold text-2xl text-slate-800 group-hover:text-brand-primary text-center">
                    {brand.name}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Category Showcase */}
        <section className="py-24 bg-slate-50">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-12 gap-4">
              <div>
                <h2 className="font-heading font-bold text-4xl text-slate-900 mb-4">Explore by Category</h2>
                <p className="text-slate-600 text-lg">Browse our extensive inventory of premium wholesale goods.</p>
              </div>
              <Link href="/products" className="hidden sm:flex text-brand-primary hover:text-brand-primary-hover font-semibold items-center gap-2">
                View All Categories <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              {categories.slice(0, 4).map((category, i) => (
                <Link key={category.id} href={`/products?category=${category.id}`} className="group relative h-64 rounded-2xl overflow-hidden bg-slate-200 shadow-sm transition-transform hover:-translate-y-1 hover:shadow-xl">
                  {/* Decorative Background Gradients */}
                  <div className={`absolute inset-0 bg-gradient-to-br ${i%2===0 ? 'from-slate-700 to-slate-900' : 'from-brand-primary to-brand-dark'} transition-transform duration-500 group-hover:scale-105`} />
                  <div className="absolute inset-0 bg-black/20 group-hover:bg-black/40 transition-colors" />
                  <div className="absolute inset-0 p-6 flex flex-col justify-end">
                    <h3 className="font-heading font-bold text-2xl text-white mb-1">{category.name}</h3>
                    <span className="text-white/80 font-medium text-sm flex items-center gap-1 group-hover:gap-2 transition-all">
                      Browse Items <ArrowRight className="w-4 h-4" />
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {/* Product Catalog Preview */}
        <section className="py-24 bg-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end mb-12 gap-4">
              <div>
                <h2 className="font-heading font-bold text-4xl text-slate-900 mb-4">Latest Arrivals</h2>
                <p className="text-slate-600 text-lg">Discover our newest wholesale offerings ready for dispatch.</p>
              </div>
              <Link href="/products" className="hidden sm:flex text-brand-primary hover:text-brand-primary-hover font-semibold items-center gap-2">
                View Catalog <ArrowRight className="w-4 h-4" />
              </Link>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
              {products.map((product) => (
                <div key={product.id} className="group flex flex-col bg-white border border-slate-200 rounded-2xl overflow-hidden hover:shadow-xl transition-all duration-300">
                  <div className="relative aspect-square bg-slate-50 p-6 flex items-center justify-center">
                    {product.image_url ? (
                      <img src={product.image_url} alt={product.name} className="object-contain max-h-full mix-blend-multiply group-hover:scale-105 transition-transform duration-500" />
                    ) : (
                      <div className="w-24 h-24 bg-slate-200 rounded-full flex items-center justify-center text-slate-400 font-medium">No Image</div>
                    )}
                  </div>
                  <div className="p-6 flex flex-col flex-1">
                    <span className="text-xs font-bold text-brand-primary uppercase tracking-wider mb-2">{product.brand || 'Unbranded'}</span>
                    <h3 className="font-heading font-bold text-lg text-slate-900 mb-2 line-clamp-2">{product.name}</h3>
                    <div className="text-sm text-slate-500 mb-6 flex-1 space-y-1">
                      <p><span className="font-medium text-slate-700">Category:</span> {product.category_name}</p>
                      <p><span className="font-medium text-slate-700">Packaging:</span> {product.unit}</p>
                    </div>
                    <button className="w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold py-2.5 rounded-lg transition-colors cursor-pointer">
                      Request Pricing
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

      </main>

      <Footer />
      <FloatingWhatsApp />
    </div>
  );
}
