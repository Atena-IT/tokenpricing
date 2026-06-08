import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex h-11 items-center justify-center rounded-2xl px-4 text-sm font-medium transition focus:outline-none",
  {
    variants: {
      variant: {
        primary: "bg-cyan-400 text-slate-950 hover:bg-cyan-300",
        secondary: "bg-white/5 text-slate-50 hover:bg-white/10",
      },
    },
    defaultVariants: {
      variant: "primary",
    },
  },
);

export function Button({ className, variant, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonVariants>) {
  return <button className={cn(buttonVariants({ variant }), className)} {...props} />;
}
