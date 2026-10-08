import Image from "next/image";
import Link from "next/link";
import { Truck, Shield, Factory } from "lucide-react";

interface Product {
  id: number;
  name: string;
  category_name: string;
  image_url: string | null;
  brand: string | null;
}

interface Brand {
  id: number;
  name: string;
  logo_url: string;
}

async function getLatestProducts(): Promise<Product[]> {
  try {
    const res = await fetch("http://localhost:5000/api/public/products", {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return (data.products || []).slice(0, 6);
  } catch (error) {
    console.error("Failed to fetch products:", error);
    return [];
  }
}

async function getBrands(): Promise<Brand[]> {
  try {
    const res = await fetch("http://localhost:5000/api/public/brands", {
      next: { revalidate: 60 },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.brands || [];
  } catch (error) {
    console.error("Failed to fetch brands:", error);
    return [];
  }
}

export default async function Home() {
  const [latestProducts, brands] = await Promise.all([
    getLatestProducts(),
    getBrands(),
  ]);

  const marqueeBrands = brands.filter((b) => b.logo_url);

  return (
    <div className="flex flex-col min-h-screen">
      {/* Hero Section */}
      <section className="relative pt-24 pb-12 flex flex-col items-center justify-center text-center px-4 overflow-hidden bg-transparent">

        {/* Headline */}
        <div className="relative z-10 max-w-4xl mx-auto flex flex-col items-center mb-12">
          <h1 className="text-5xl sm:text-7xl md:text-[80px] font-bold text-white tracking-tighter leading-none drop-shadow-sm">
            Wholesale, refined.
          </h1>
        </div>

        {/* Hero Image with subtle side and edge blends */}
        <div className="relative w-full max-w-full mx-auto z-10 px-0 mb-16">
          <div
            className="relative w-full overflow-hidden"
            style={{
              WebkitMaskImage: 'linear-gradient(to right, transparent 0%, black 2%, black 98%, transparent 100%)',
              maskImage: 'linear-gradient(to right, transparent 0%, black 2%, black 98%, transparent 100%)'
            }}
          >
            <div
              className="relative w-full"
              style={{
                WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%)',
                maskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 95%, transparent 100%)'
              }}
            >
              <Image
                src="/images/hero_bg_new.jpg"
                alt="Wholesale Distribution"
                width={1920}
                height={1080}
                className="w-full h-auto object-contain"
                priority
                sizes="100vw"
              />
              {/* Subtle edge blend overlay */}
              <div className="absolute inset-y-0 left-0 w-4 sm:w-8 bg-gradient-to-r from-[#064e3b]/50 to-transparent pointer-events-none" />
              <div className="absolute inset-y-0 right-0 w-4 sm:w-8 bg-gradient-to-l from-[#064e3b]/50 to-transparent pointer-events-none" />
              <div className="absolute inset-x-0 top-0 h-6 sm:h-12 bg-gradient-to-b from-[#064e3b]/40 to-transparent pointer-events-none" />
              <div className="absolute inset-x-0 bottom-0 h-6 sm:h-12 bg-gradient-to-t from-[#064e3b]/40 to-transparent pointer-events-none" />
            </div>
          </div>
        </div>

        {/* Subtext and Button */}
        <div className="relative z-10 max-w-2xl mx-auto flex flex-col items-center mb-12">
          <p className="text-xl sm:text-2xl text-emerald-100/90 mb-10 font-light tracking-tight">
            Premium equipment and supplies for discerning businesses across Northern California.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/products"
              className="inline-flex items-center justify-center rounded-full bg-white hover:bg-emerald-50 text-emerald-950 font-semibold px-8 py-4 text-lg transition-transform active:scale-95 shadow-xl hover:shadow-2xl"
            >
              Shop Wholesale
            </Link>
          </div>
        </div>
      </section>

      {/* Marquee Section */}
      <section className="py-16 bg-white/90 backdrop-blur-md border-y border-white/20 overflow-hidden relative group">

        {/* The Marquee (Single Layer, Full Color) */}
        <div className="mobile-marquee flex w-max items-center whitespace-nowrap group-hover:[animation-play-state:paused]">
          {[...marqueeBrands, ...marqueeBrands, ...marqueeBrands, ...marqueeBrands].map((brand, i) => (
            <Link key={i} href={`/products?brand=${encodeURIComponent(brand.name)}`} className="mx-8 md:mx-12 shrink-0 transition-transform hover:scale-105">
              <Image
                src={brand.logo_url}
                alt={brand.name}
                width={140}
                height={70}
                unoptimized
                className="object-contain h-12 md:h-14 w-auto mix-blend-multiply"
              />
            </Link>
          ))}
        </div>

        {/* Grayscale Color Overlay (Reveals center in full color) */}
        <div
          className="absolute inset-0 z-10 pointer-events-none mix-blend-color opacity-80"
          style={{
            background: "linear-gradient(to right, #808080 0%, #808080 30%, transparent 45%, transparent 55%, #808080 70%, #808080 100%)"
          }}
        />

        {/* Fade Edges to blend with background */}
        <div className="absolute top-0 left-0 bottom-0 w-16 md:w-32 bg-gradient-to-r from-white to-transparent z-20 pointer-events-none" />
        <div className="absolute top-0 right-0 bottom-0 w-16 md:w-32 bg-gradient-to-l from-white to-transparent z-20 pointer-events-none" />
      </section>

      {/* Utility Grid Features */}
      <section className="py-28 bg-transparent px-4">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-3 gap-6">
            {/* Feature 1 */}
            <div className="bg-white/95 backdrop-blur-md rounded-[18px] p-10 border border-white/40 shadow-xl flex flex-col items-center text-center hover:bg-white transition-all">
              <div className="text-emerald-700 mb-6">
                <Truck className="w-10 h-10 stroke-1" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">Fast Dispatch.</h3>
              <p className="text-gray-600 text-lg leading-relaxed">Next-day delivery optimized for Northern California.</p>
            </div>

            {/* Feature 2 */}
            <div className="bg-white/95 backdrop-blur-md rounded-[18px] p-10 border border-white/40 shadow-xl flex flex-col items-center text-center hover:bg-white transition-all">
              <div className="text-emerald-700 mb-6">
                <Shield className="w-10 h-10 stroke-1" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">Verified Quality.</h3>
              <p className="text-gray-600 text-lg leading-relaxed">Rigorous quality control for every batch you order.</p>
            </div>

            {/* Feature 3 */}
            <div className="bg-white/95 backdrop-blur-md rounded-[18px] p-10 border border-white/40 shadow-xl flex flex-col items-center text-center hover:bg-white transition-all">
              <div className="text-emerald-700 mb-6">
                <Factory className="w-10 h-10 stroke-1" />
              </div>
              <h3 className="text-2xl font-bold text-gray-900 mb-3 tracking-tight">Direct Sourcing.</h3>
              <p className="text-gray-600 text-lg leading-relaxed">Exclusive manufacturer partnerships for unbeatable margins.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Latest Arrivals */}
      <section className="py-28 bg-transparent px-4">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-5xl font-bold text-white mb-4 tracking-tighter drop-shadow-sm">Latest Arrivals.</h2>
            <Link href="/products" className="text-emerald-200 font-medium hover:text-white hover:underline underline-offset-4 text-lg">
              Explore the Collection &gt;
            </Link>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {latestProducts.map((product) => (
              <Link key={product.id} href={`/products?brand=${encodeURIComponent(product.brand || '')}`} className="group block">
                <div className="bg-white/95 backdrop-blur-md rounded-[18px] overflow-hidden flex flex-col h-full border border-white/30 shadow-xl hover:shadow-2xl transition-all duration-500">
                  <div className="aspect-[4/3] bg-white relative p-8 flex items-center justify-center">
                    {product.image_url ? (
                      <Image
                        src={product.image_url}
                        alt={product.name}
                        fill
                        unoptimized
                        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
                        className="object-contain p-8 group-hover:scale-105 transition-transform duration-700 drop-shadow-xl"
                      />
                    ) : (
                      <div className="text-2xl font-bold text-muted uppercase text-center tracking-tighter">
                        {product.name}
                      </div>
                    )}
                  </div>
                  <div className="p-8 pt-4 flex flex-col flex-1 text-center bg-white/95">
                    <span className="text-xs font-semibold text-emerald-800 uppercase tracking-widest mb-3">{product.brand || 'Unbranded'}</span>
                    <h3 className="font-bold text-xl text-gray-900 mb-1 tracking-tight">{product.name}</h3>
                    <p className="text-base text-gray-500 mt-1">{product.category_name}</p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
