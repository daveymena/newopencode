import { useState, useEffect } from 'react';
import { useListModels, useListSessions, useCreateSession } from '@workspace/api-client-react/src/generated/api';
import { FileExplorer } from '@/components/FileExplorer';
import { CodeEditorPanel } from '@/components/CodeEditor';
import { TerminalPanel } from '@/components/Terminal';
import { ChatPanel } from '@/components/ChatPanel';
import { Terminal, Plus, LayoutGrid } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { getListSessionsQueryKey } from '@workspace/api-client-react/src/generated/api';

export function Workspace() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('claude-sonnet-4-6');
  const [activeFilePath, setActiveFilePath] = useState<string | null>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);

  const queryClient = useQueryClient();

  const { data: modelsData } = useListModels();
  const { data: sessionsData, isLoading: sessionsLoading } = useListSessions();
  const { mutateAsync: createSession, isPending: isCreatingSession } = useCreateSession();

  // Auto-select first session if none selected and sessions exist
  useEffect(() => {
    if (!activeSessionId && sessionsData?.sessions?.length && sessionsData.sessions.length > 0) {
      setActiveSessionId(sessionsData.sessions[0].id);
      setSelectedModel(sessionsData.sessions[0].model || 'claude-sonnet-4-6');
    }
  }, [sessionsData, activeSessionId]);

  const handleCreateSession = async () => {
    try {
      const newSession = await createSession({
        data: {
          title: `Session ${new Date().toLocaleTimeString()}`,
          model: selectedModel
        }
      });
      setActiveSessionId(newSession.id);
      queryClient.invalidateQueries({ queryKey: getListSessionsQueryKey() });
    } catch (err) {
      console.error("Failed to create session", err);
    }
  };

  return (
    <div className="flex flex-col h-screen w-full bg-background overflow-hidden selection:bg-primary/30">
      
      {/* Top Navbar */}
      <nav className="h-12 border-b border-border bg-card flex items-center justify-between px-4 shrink-0 shadow-sm z-10">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 font-bold text-primary">
            <Terminal className="w-5 h-5" />
            <span className="tracking-tight text-lg hidden sm:inline-block">OpenCode</span>
          </div>
          
          <button 
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-1.5 text-muted-foreground hover:bg-muted rounded-md transition-colors sm:hidden"
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center gap-4">
          {/* Model Selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground hidden md:inline-block font-mono">MODEL:</span>
            <select 
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-background border border-border rounded-md px-2 py-1 text-xs font-mono focus:ring-1 focus:ring-primary outline-none text-foreground w-[160px]"
            >
              {modelsData?.models?.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
              {!modelsData?.models?.length && <option value="claude-sonnet-4-6">claude-sonnet-4-6</option>}
            </select>
          </div>

          {/* Session Selector */}
          <div className="flex items-center gap-2 border-l border-border pl-4">
            <select
              value={activeSessionId || ''}
              onChange={(e) => setActiveSessionId(e.target.value)}
              className="bg-background border border-border rounded-md px-2 py-1 text-xs focus:ring-1 focus:ring-primary outline-none text-foreground max-w-[150px]"
              disabled={sessionsLoading}
            >
              <option value="" disabled>Select Session</option>
              {sessionsData?.sessions?.map(s => (
                <option key={s.id} value={s.id}>{s.title}</option>
              ))}
            </select>
            
            <button 
              onClick={handleCreateSession}
              disabled={isCreatingSession}
              className="p-1.5 bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground rounded-md transition-all border border-primary/20"
              title="New Session"
            >
              {isCreatingSession ? <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>
      </nav>

      {/* Main Workspace Area */}
      <div className="flex-1 flex overflow-hidden">
        
        {/* Left Sidebar - File Explorer */}
        <div className={`w-64 shrink-0 transition-all duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : '-ml-64 absolute h-full z-20'}`}>
          <FileExplorer 
            onFileSelect={(path) => {
              setActiveFilePath(path);
              if (window.innerWidth < 640) setIsSidebarOpen(false); // auto-close on mobile
            }}
            activeFile={activeFilePath}
          />
        </div>

        {/* Center Panel - Editor & Terminal */}
        <div className="flex-1 flex flex-col min-w-0">
          <CodeEditorPanel filePath={activeFilePath} />
          <TerminalPanel className="h-[250px] shrink-0" />
        </div>

        {/* Right Sidebar - Chat */}
        <div className="w-80 lg:w-[400px] shrink-0 hidden md:block">
          <ChatPanel sessionId={activeSessionId} selectedModel={selectedModel} />
        </div>
        
      </div>
    </div>
  );
}
