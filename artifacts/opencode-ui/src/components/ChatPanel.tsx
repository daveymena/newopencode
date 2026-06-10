import { useState, useRef, useEffect } from 'react';
import { useGetMessages } from '@workspace/api-client-react/src/generated/api';
import { useChatStream } from '@/hooks/use-chat-stream';
import { Send, Bot, User, StopCircle, Sparkles, TerminalSquare } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface ChatPanelProps {
  sessionId: string | null;
  selectedModel: string;
}

export function ChatPanel({ sessionId, selectedModel }: ChatPanelProps) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { data, isLoading } = useGetMessages(sessionId || '', {
    query: { enabled: !!sessionId }
  });
  
  const { sendMessage, stopStream, isStreaming, currentStream } = useChatStream();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [data?.messages, currentStream]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || isStreaming) return;
    
    sendMessage({
      sessionId,
      message: input,
      model: selectedModel
    });
    
    setInput('');
  };

  if (!sessionId) {
    return (
      <div className="flex flex-col h-full bg-card border-l border-border justify-center items-center p-6 text-center">
        <div className="w-16 h-16 bg-muted/30 rounded-2xl flex items-center justify-center mb-4 text-muted-foreground border border-border">
          <TerminalSquare className="w-8 h-8" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">No Active Session</h3>
        <p className="text-sm text-muted-foreground mt-2 max-w-[250px]">
          Create or select a session to start collaborating with OpenCode AI.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-card border-l border-border shadow-2xl shadow-black/20">
      {/* Header */}
      <div className="p-4 border-b border-border flex items-center gap-3 shrink-0">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center border border-primary/20">
          <Sparkles className="w-4 h-4 text-primary" />
        </div>
        <div>
          <h2 className="text-sm font-bold text-foreground">AI Assistant</h2>
          <p className="text-xs text-muted-foreground font-mono">{selectedModel}</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {isLoading ? (
          <div className="flex justify-center py-8">
            <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <>
            {data?.messages?.length === 0 && !currentStream && (
              <div className="h-full flex flex-col items-center justify-center text-muted-foreground text-center">
                <p>Start the conversation.</p>
                <p className="text-xs mt-1">Ask me to write code, explain files, or run commands.</p>
              </div>
            )}
            
            {data?.messages?.map((msg, idx) => (
              <div key={msg.id || idx} className={cn(
                "flex gap-3 max-w-[90%]",
                msg.role === 'user' ? "ml-auto flex-row-reverse" : "mr-auto"
              )}>
                <div className={cn(
                  "w-8 h-8 rounded-full flex items-center justify-center shrink-0 border",
                  msg.role === 'user' 
                    ? "bg-secondary border-secondary-foreground/10 text-secondary-foreground" 
                    : "bg-primary/10 border-primary/20 text-primary"
                )}>
                  {msg.role === 'user' ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>
                
                <div className={cn(
                  "rounded-2xl px-4 py-3 text-sm",
                  msg.role === 'user' 
                    ? "bg-secondary text-secondary-foreground rounded-tr-sm" 
                    : "bg-muted/30 border border-border text-foreground rounded-tl-sm w-full overflow-hidden"
                )}>
                  {msg.role === 'user' ? (
                    <p className="whitespace-pre-wrap">{msg.content}</p>
                  ) : (
                    <div className="prose prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {/* Streaming message indicator */}
            {isStreaming && (
              <div className="flex gap-3 max-w-[90%] mr-auto">
                <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 border bg-primary/10 border-primary/20 text-primary">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="rounded-2xl rounded-tl-sm px-4 py-3 text-sm bg-muted/30 border border-border text-foreground w-full overflow-hidden">
                  {currentStream ? (
                    <div className="prose prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {currentStream + " ▍"}
                      </ReactMarkdown>
                    </div>
                  ) : (
                    <div className="flex items-center gap-1 h-5">
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/50 animate-bounce" />
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/50 animate-bounce" style={{ animationDelay: '150ms' }} />
                      <div className="w-1.5 h-1.5 rounded-full bg-primary/50 animate-bounce" style={{ animationDelay: '300ms' }} />
                    </div>
                  )}
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Form */}
      <div className="p-4 border-t border-border bg-card/50">
        <form onSubmit={handleSubmit} className="relative flex items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSubmit(e as any);
              }
            }}
            placeholder="Ask OpenCode anything..."
            disabled={isStreaming}
            className="w-full min-h-[60px] max-h-[200px] bg-background border border-border rounded-xl px-4 py-3 pr-12 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/50 transition-all custom-scrollbar disabled:opacity-50"
            rows={2}
          />
          
          <div className="absolute right-2 bottom-2">
            {isStreaming ? (
              <button 
                type="button" 
                onClick={stopStream}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors shadow-sm"
              >
                <StopCircle className="w-4 h-4" />
              </button>
            ) : (
              <button 
                type="submit" 
                disabled={!input.trim()}
                className="w-8 h-8 flex items-center justify-center rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
              >
                <Send className="w-4 h-4 ml-0.5" />
              </button>
            )}
          </div>
        </form>
        <p className="text-[10px] text-center text-muted-foreground mt-2 font-mono opacity-50">
          Return to send, Shift+Return for newline
        </p>
      </div>
    </div>
  );
}
