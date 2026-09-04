import { ReactNode } from "react";
import { ArrowRightIcon } from "lucide-react";
import { cn } from "@/lib/utils";

const BentoGrid = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) => {
  return (
    <div
      className={cn(
        "grid w-full grid-cols-1 md:grid-cols-3 gap-6",
        className,
      )}
    >
      {children}
    </div>
  );
};

const BentoCard = ({
  name,
  className,
  background,
  Icon,
  description,
  href,
  cta,
}: {
  name: string;
  className?: string;
  background: ReactNode;
  Icon: any;
  description: string;
  href?: string;
  cta?: string;
}) => (
  <div
    key={name}
    className={cn(
      "group relative col-span-1 flex flex-col p-6 sm:p-7 overflow-hidden rounded-2xl transition-all duration-300 hover:shadow-md",
      "bg-white border border-slate-200/80 shadow-sm",
      className,
    )}
  >
    <div>{background}</div>
    <div className="relative z-10 flex flex-col gap-3">
      <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-brand-primary">
        <Icon className="h-6 w-6" />
      </div>
      <h3 className="text-xl font-bold font-heading text-slate-900">
        {name}
      </h3>
      <p className="text-sm text-slate-600 leading-relaxed">{description}</p>
    </div>

    <div className="pointer-events-none absolute inset-0 transition-all duration-300 group-hover:bg-slate-50/50" />
  </div>
);

export { BentoCard, BentoGrid };
