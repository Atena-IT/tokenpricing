import type { InputHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-11 w-full rounded-2xl border border-white/10 bg-white/5 px-4 text-sm text-slate-50 outline-none transition placeholder:text-slate-400 focus:border-cyan-400/50",
        className,
      )}
      {...props}
    />
  );
}
