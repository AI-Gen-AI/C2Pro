import * as React from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps extends React.HTMLAttributes<HTMLDivElement> {
  icon?: LucideIcon | React.ComponentType<{ className?: string }> | React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
  ...props
}: EmptyStateProps) {
  const renderIcon = () => {
    if (!Icon) return null;
    if (typeof Icon === "function" || (Icon && typeof Icon === "object" && ("render" in Icon || "$$typeof" in Icon))) {
      const IconComponent = Icon as React.ComponentType<{ className?: string }>;
      return <IconComponent className="h-10 w-10 text-muted-foreground/50" />;
    }
    return Icon;
  };

  const renderedIcon = renderIcon();

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed bg-card py-16 px-4 text-center",
        className
      )}
      {...props}
    >
      {renderedIcon && (
        <div className="mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-muted/50">
          {renderedIcon}
        </div>
      )}
      <h3 className="text-sm font-medium text-foreground tracking-tight">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">
        {description}
      </p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}
