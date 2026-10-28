import { GlobalNav } from "@/components/GlobalNav";

export default function MarketingLayout({ children }: LayoutProps<"/">) {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-50">
      <GlobalNav />
      {children}
    </div>
  );
}
