"use client";

/**
 * Test Suite ID: TASK-FRT-199
 * Backlog Task: TASK-FRT-199
 */
import {
  type ComponentPropsWithoutRef,
  type ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";

type RevealProps = ComponentPropsWithoutRef<"div"> & {
  children: ReactNode;
};

export function Reveal({ children, className, ...props }: RevealProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [isInView, setIsInView] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    setReducedMotion(prefersReducedMotion);

    if (prefersReducedMotion) {
      setIsInView(true);
      return;
    }

    const node = ref.current;
    if (!node || !("IntersectionObserver" in window)) {
      setIsInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setIsInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      className={cn(
        "opacity-100 translate-y-0",
        !reducedMotion &&
          !isInView &&
          "motion-safe:opacity-0 motion-safe:translate-y-3 motion-safe:transition motion-safe:duration-500 motion-safe:ease-out",
        isInView && "opacity-100 translate-y-0",
        className,
      )}
      ref={ref}
      {...props}
    >
      {children}
    </div>
  );
}
