import BlurFade from "@/components/magicui/blur-fade";
import Link from "next/link";
import { ArrowRight } from "lucide-react";

export default function Terms() {
  return (
    <div className="bg-slate-50 min-h-screen pb-24">
      <div className="relative w-full h-[400px] flex flex-col items-center justify-center overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-900/90 to-slate-950 z-10" />
        <div className="relative z-20 text-center px-4">
          <BlurFade delay={0.1}>
            <h1 className="font-heading text-5xl md:text-6xl font-extrabold mb-4">Terms of Trade</h1>
            <p className="text-slate-300 text-lg max-w-2xl mx-auto font-light">
              General terms and conditions for wholesale distribution.
            </p>
          </BlurFade>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <BlurFade delay={0.2}>
          <div className="bg-white rounded-2xl p-8 md:p-12 border border-slate-100 shadow-sm prose prose-slate max-w-none">
            <p className="lead text-lg text-slate-600 mb-8">
              Welcome to AK Distributors LLC. The following terms and conditions govern the sale and delivery of goods from AK Distributors LLC to the Customer. By placing an order with us, the Customer agrees to be bound by these terms.
            </p>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">1. Pricing and Payment Terms</h3>
            <p className="text-slate-700">
              All prices are subject to change without prior notice. The price charged will be the price in effect at the time the order is accepted.
            </p>
            <ul className="text-slate-700">
              <li><strong>Cash/COD Customers:</strong> Payment is due in full at the time of delivery.</li>
              <li><strong>Credit Customers:</strong> For approved credit accounts, payment terms are strictly net as indicated on the invoice. Failure to pay within the agreed timeframe may result in suspension of the account and compounding late fees.</li>
            </ul>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">2. Minimum Orders and Delivery</h3>
            <p className="text-slate-700">
              AK Distributors provides delivery services to verified commercial addresses. Minimum order quantities or values may apply for free delivery.
              We reserve the right to refuse delivery to non-commercial addresses or locations outside our standard delivery zones without an additional surcharge.
            </p>
            
            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">3. Shortages, Damages, and Returns</h3>
            <p className="text-slate-700">
              It is the Customer's responsibility to inspect all goods immediately upon delivery. 
              Any claims for shortages, damages, or discrepancies must be reported to the driver at the time of delivery and noted on the invoice.
            </p>
            <ul className="text-slate-700">
              <li>No returns will be accepted after 48 hours of delivery.</li>
              <li>Returned goods must be in their original packaging and in resalable condition.</li>
              <li>Perishable goods cannot be returned unless proven defective at the time of delivery.</li>
            </ul>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">4. Title and Risk</h3>
            <p className="text-slate-700">
              Risk of loss or damage to the goods passes to the Customer upon delivery. However, title and ownership of the goods remain with AK Distributors LLC until payment is received in full. 
            </p>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">5. Limitation of Liability</h3>
            <p className="text-slate-700">
              AK Distributors LLC shall not be liable for any indirect, special, or consequential damages arising out of the sale, delivery, or use of the products. Our total liability shall not exceed the purchase price of the specific goods in question.
            </p>
          </div>

          <div className="mt-12 text-center">
            <p className="text-slate-500 mb-6">If you have any questions regarding these terms, please contact our support team.</p>
            <Link href="/contact" className="inline-flex bg-slate-900 hover:bg-slate-800 text-white px-8 py-3 rounded-full font-semibold transition-colors items-center justify-center gap-2">
              Contact Us <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </BlurFade>
      </div>
    </div>
  );
}
