import { Link } from "wouter";
import { TerminalSquare } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen w-full flex flex-col items-center justify-center bg-background text-foreground">
      <TerminalSquare className="w-24 h-24 text-muted-foreground mb-8 opacity-50" />
      <h1 className="text-4xl font-bold tracking-tight mb-2">404</h1>
      <p className="text-xl text-muted-foreground font-mono mb-8">System Error: Path not resolved</p>
      
      <Link href="/" className="px-6 py-3 rounded-lg font-medium bg-primary text-primary-foreground hover:bg-primary/90 hover:-translate-y-0.5 transition-all shadow-lg shadow-primary/25">
        Return to Workspace
      </Link>
    </div>
  );
}
