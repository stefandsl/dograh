"use client";

import Image from "next/image";

import { cn } from "@/lib/utils";

const LOGO_IMAGE_CLASS = cn(
  "relative z-10 object-contain",
  "drop-shadow-[0_2px_14px_rgba(14,165,233,0.38)]",
  "dark:brightness-[1.16] dark:contrast-[1.24]",
  "dark:drop-shadow-[0_0_2px_rgba(255,255,255,0.72),0_0_22px_rgba(56,189,248,0.68),0_0_36px_rgba(14,165,233,0.35)]"
);

function MaskedRotatingGlow({
  className,
  glowClassName = "bellerophone-logo-glow",
  spinClassName,
}: {
  className?: string;
  glowClassName?: string;
  spinClassName?: string;
}) {
  return (
    <div
      className={cn("bellerophone-logo-glow-mask pointer-events-none absolute inset-0", className)}
      aria-hidden
    >
      <div
        className={cn(
          glowClassName,
          "absolute inset-[-100%]",
          spinClassName ?? "animate-spin-border-idle group-hover/logo:animate-spin-slow"
        )}
      />
    </div>
  );
}

type BellerophoneLogoFrameProps = {
  alt: string;
  collapsed?: boolean;
  className?: string;
};

/** Winged-B logo with always-on neon cyan glow traced to the PNG silhouette (mask-based). */
export function BellerophoneLogoFrame({
  alt,
  collapsed = false,
  className,
}: BellerophoneLogoFrameProps) {
  return (
    <div
      className={cn(
        "group/logo relative shrink-0 overflow-visible",
        collapsed ? "size-8" : "max-h-20 w-full max-w-[78%]",
        className
      )}
    >
      <MaskedRotatingGlow
        className="-inset-[14%] opacity-50 blur-2xl dark:opacity-65"
        glowClassName="bellerophone-logo-glow-halo"
        spinClassName="animate-spin-border-idle [animation-duration:11s] group-hover/logo:animate-spin-slow"
      />

      <MaskedRotatingGlow
        className="opacity-80 blur-[6px] dark:opacity-95"
        spinClassName="animate-spin-border-idle group-hover/logo:animate-spin-slow"
      />

      <MaskedRotatingGlow
        className="-inset-[10%] opacity-65 blur-lg dark:opacity-80"
        spinClassName="animate-spin-border-idle group-hover/logo:animate-spin-slow [animation-direction:reverse] [animation-duration:10s]"
      />

      <MaskedRotatingGlow className="opacity-95 dark:opacity-100" />

      <Image
        src="/bellerophone-logo.png"
        alt={alt}
        width={collapsed ? 32 : 112}
        height={collapsed ? 32 : 112}
        className={cn(
          LOGO_IMAGE_CLASS,
          collapsed ? "size-full" : "h-auto max-h-20 w-full"
        )}
      />
    </div>
  );
}
