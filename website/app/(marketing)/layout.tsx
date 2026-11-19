import { GlobalNav } from "@/components/GlobalNav";
import { SiteFooter } from "@/components/SiteFooter";

export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <a href="#main-content" className="skip-link">Skip to content</a>
      <GlobalNav />
      {children}
      <SiteFooter />
    </div>
  );
}
