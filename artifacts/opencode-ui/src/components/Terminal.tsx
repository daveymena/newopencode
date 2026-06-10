import { useState, useRef, useEffect } from 'react';
import { useExecuteCommand } from '@workspace/api-client-react/src/generated/api';
import { Terminal as TerminalIcon, Play, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface OutputLine {
  id: string;
  type: 'command' | 'stdout' | 'stderr' | 'system';
  content: string;
}

export function TerminalPanel({ className }: { className?: string }) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [input, setInput] = useState('');
  const [history, setHistory] = useState<OutputLine[]>([
    { id: 'start', type: 'system', content: 'OpenCode Terminal Ready.' }
  ]);
  const endOfOutputRef = useRef<HTMLDivElement>(null);
  
  const { mutateAsync: executeCmd, isPending } = useExecuteCommand();

  const scrollToBottom = () => {
    endOfOutputRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [history, isExpanded]);

  const handleCommand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isPending) return;

    const cmd = input.trim();
    setInput('');
    
    if (cmd === 'clear') {
      setHistory([]);
      return;
    }

    setHistory(prev => [...prev, { id: Date.now().toString(), type: 'command', content: `$ ${cmd}` }]);

    try {
      const res = await executeCmd({ data: { command: cmd } });
      if (res.stdout) {
        setHistory(prev => [...prev, { id: `${Date.now()}-out`, type: 'stdout', content: res.stdout }]);
      }
      if (res.stderr) {
        setHistory(prev => [...prev, { id: `${Date.now()}-err`, type: 'stderr', content: res.stderr }]);
      }
      if (!res.stdout && !res.stderr && res.exitCode === 0) {
        setHistory(prev => [...prev, { id: `${Date.now()}-sys`, type: 'system', content: `[Process exited with code 0]` }]);
      }
    } catch (err: any) {
      setHistory(prev => [...prev, { id: `${Date.now()}-err`, type: 'stderr', content: err.message || 'Failed to execute command' }]);
    }
  };

  if (!isExpanded) {
    return (
      <div className={cn("bg-card border-t border-border flex items-center justify-between px-4 py-2 text-sm text-muted-foreground hover:bg-muted/30 cursor-pointer transition-colors", className)} onClick={() => setIsExpanded(true)}>
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-4 h-4" />
          <span>Terminal</span>
        </div>
        <ChevronUp className="w-4 h-4" />
      </div>
    );
  }

  return (
    <div className={cn("bg-[#0A0A0A] border-t border-border flex flex-col font-mono text-sm", className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card/50">
        <div className="flex items-center gap-2 text-muted-foreground">
          <TerminalIcon className="w-4 h-4" />
          <span className="text-xs uppercase tracking-wider font-semibold text-foreground/80">Terminal</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setHistory([])} className="text-muted-foreground hover:text-foreground transition-colors p-1" title="Clear">
            <XCircle className="w-4 h-4" />
          </button>
          <button onClick={() => setIsExpanded(false)} className="text-muted-foreground hover:text-foreground transition-colors p-1" title="Collapse">
            <ChevronDown className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Output Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {history.map(line => (
          <div key={line.id} className={cn(
            "whitespace-pre-wrap break-words",
            line.type === 'command' && "text-primary",
            line.type === 'stdout' && "text-foreground",
            line.type === 'stderr' && "text-destructive",
            line.type === 'system' && "text-muted-foreground italic"
          )}>
            {line.content}
          </div>
        ))}
        <div ref={endOfOutputRef} />
      </div>

      {/* Input Area */}
      <form onSubmit={handleCommand} className="flex items-center px-4 py-2 border-t border-border bg-[#0A0A0A]">
        <span className="text-primary mr-2 font-bold select-none">{'>'}</span>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={isPending ? "Executing..." : "Enter command..."}
          disabled={isPending}
          className="flex-1 bg-transparent border-none outline-none text-foreground placeholder:text-muted-foreground/50 disabled:opacity-50"
          autoComplete="off"
          spellCheck="false"
        />
        {isPending && <div className="w-2 h-4 bg-primary animate-pulse ml-2" />}
      </form>
    </div>
  );
}
