import BlurFade from "@/components/magicui/blur-fade";
import Link from "next/link";

export default function Privacy() {
  return (
    <div className="bg-slate-50 min-h-screen pb-24">
      <div className="relative w-full h-[400px] flex flex-col items-center justify-center overflow-hidden bg-slate-950 text-white">
        <div className="absolute inset-0 bg-gradient-to-b from-slate-950 via-slate-900/90 to-slate-950 z-10" />
        <div className="relative z-20 text-center px-4">
          <BlurFade delay={0.1}>
            <h1 className="font-heading text-5xl md:text-6xl font-extrabold mb-4">Privacy Policy</h1>
            <p className="text-slate-300 text-lg max-w-2xl mx-auto font-light">
              How we collect, use, and protect your data.
            </p>
          </BlurFade>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <BlurFade delay={0.2}>
          <div className="bg-white rounded-2xl p-8 md:p-12 border border-slate-100 shadow-sm prose prose-slate max-w-none">
            
            <p className="text-slate-500 text-sm mb-8">Last Updated: {new Date().toLocaleDateString()}</p>

            <p className="lead text-lg text-slate-600 mb-8">
              At AK Distributors LLC, we are committed to protecting your privacy and ensuring that your personal and business information is handled safely and responsibly.
            </p>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">1. Information We Collect</h3>
            <p className="text-slate-700">
              We collect information necessary to establish business accounts, process orders, and provide delivery services. This may include:
            </p>
            <ul className="text-slate-700">
              <li><strong>Contact Information:</strong> Names, business addresses, email addresses, and phone numbers.</li>
              <li><strong>Financial Information:</strong> Credit references, tax IDs, and payment details required for establishing credit lines or processing payments.</li>
              <li><strong>Usage Data:</strong> Information on how you interact with our website and client portal.</li>
            </ul>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">2. How We Use Your Information</h3>
            <p className="text-slate-700">
              The information we collect is used strictly for business operations, including:
            </p>
            <ul className="text-slate-700">
              <li>Fulfilling wholesale orders and coordinating deliveries.</li>
              <li>Processing invoices, payments, and managing credit accounts.</li>
              <li>Communicating important updates about products, pricing, or operational changes.</li>
              <li>Improving our website and customer service experience.</li>
            </ul>
            
            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">3. Data Sharing</h3>
            <p className="text-slate-700">
              We do not sell, rent, or trade your personal or business information to third parties. We may share necessary information with trusted third-party service providers (such as shipping partners or payment processors) solely for the purpose of fulfilling your order. 
            </p>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">4. Data Security</h3>
            <p className="text-slate-700">
              We implement industry-standard security measures to protect your data from unauthorized access, alteration, disclosure, or destruction. Access to financial and personal information is restricted to authorized personnel only.
            </p>

            <h3 className="font-heading text-2xl font-bold text-slate-900 mt-8 mb-4">5. Your Rights</h3>
            <p className="text-slate-700">
              You have the right to request access to the information we hold about your business, and to request corrections if the information is inaccurate. To update your account details, please contact our support team.
            </p>

            <div className="mt-12 p-6 bg-slate-50 border border-slate-100 rounded-xl">
              <h4 className="font-heading text-lg font-bold text-slate-900 mb-2">Contact Us About Privacy</h4>
              <p className="text-slate-600 mb-0">
                If you have any questions or concerns about our Privacy Policy, please contact us at <a href="mailto:akdistributorsusa@gmail.com" className="text-brand-primary font-medium hover:underline">akdistributorsusa@gmail.com</a>.
              </p>
            </div>
          </div>
        </BlurFade>
      </div>
    </div>
  );
}
