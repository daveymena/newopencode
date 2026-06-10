import { useState, useEffect, useCallback } from 'react';
import CodeMirror from '@uiw/react-codemirror';
import { vscodeDark } from '@uiw/codemirror-theme-vscode';
import { javascript } from '@codemirror/lang-javascript';
import { html } from '@codemirror/lang-html';
import { css } from '@codemirror/lang-css';
import { python } from '@codemirror/lang-python';
import { useReadFile, useWriteFile } from '@workspace/api-client-react/src/generated/api';
import { Save, AlertCircle } from 'lucide-react';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface CodeEditorProps {
  filePath: string | null;
}

export function CodeEditorPanel({ filePath }: CodeEditorProps) {
  const [content, setContent] = useState('');
  const [isDirty, setIsDirty] = useState(false);
  
  const { data, isLoading, error } = useReadFile(
    { path: filePath || '' },
    { query: { enabled: !!filePath } }
  );

  const { mutateAsync: saveFile, isPending: isSaving } = useWriteFile();

  // Reset content when file changes
  useEffect(() => {
    if (data?.content !== undefined) {
      setContent(data.content);
      setIsDirty(false);
    }
  }, [data?.content, filePath]);

  const handleChange = useCallback((val: string) => {
    setContent(val);
    if (val !== data?.content) {
      setIsDirty(true);
    } else {
      setIsDirty(false);
    }
  }, [data?.content]);

  const handleSave = async () => {
    if (!filePath || !isDirty) return;
    try {
      await saveFile({ data: { path: filePath, content } });
      setIsDirty(false);
    } catch (err) {
      console.error("Failed to save", err);
    }
  };

  // Keyboard shortcut for save
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSave]);

  const getLanguageExtension = (path: string) => {
    if (path.endsWith('.js') || path.endsWith('.jsx') || path.endsWith('.ts') || path.endsWith('.tsx')) return [javascript({ jsx: true, typescript: true })];
    if (path.endsWith('.html')) return [html()];
    if (path.endsWith('.css')) return [css()];
    if (path.endsWith('.py')) return [python()];
    return [];
  };

  if (!filePath) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[#1e1e1e] text-muted-foreground">
        <div className="w-16 h-16 rounded-full bg-muted/20 flex items-center justify-center mb-4 border border-border/50">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinelinejoin="round"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
        </div>
        <p className="text-lg font-medium text-foreground/80">Select a file to edit</p>
        <p className="text-sm mt-2 opacity-70">OpenCode Workspace</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#1e1e1e]">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-muted-foreground">Loading {filePath}...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#1e1e1e]">
        <div className="flex flex-col items-center gap-3 text-destructive max-w-md text-center p-6 bg-destructive/10 rounded-xl border border-destructive/20">
          <AlertCircle className="w-8 h-8" />
          <p className="font-medium">Failed to read file</p>
          <p className="text-sm opacity-80">{filePath}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-[#1e1e1e] overflow-hidden relative">
      {/* Editor Header */}
      <div className="h-10 flex items-center justify-between px-4 bg-card border-b border-border shrink-0 select-none">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-foreground/90 font-mono">{filePath.split('/').pop()}</span>
          {isDirty && <span className="w-2 h-2 rounded-full bg-primary animate-pulse" title="Unsaved changes" />}
        </div>
        
        <button
          onClick={handleSave}
          disabled={!isDirty || isSaving}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all",
            isDirty 
              ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-sm shadow-primary/20" 
              : "bg-muted text-muted-foreground cursor-not-allowed opacity-50"
          )}
        >
          {isSaving ? (
            <div className="w-3.5 h-3.5 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <Save className="w-3.5 h-3.5" />
          )}
          <span>Save</span>
        </button>
      </div>
      
      {/* Editor Content */}
      <div className="flex-1 overflow-auto bg-[#1e1e1e] custom-scrollbar relative">
        <CodeMirror
          value={content}
          height="100%"
          theme={vscodeDark}
          extensions={getLanguageExtension(filePath)}
          onChange={handleChange}
          className="text-sm"
          basicSetup={{
            lineNumbers: true,
            highlightActiveLineGutter: true,
            foldGutter: true,
            dropCursor: true,
            allowMultipleSelections: true,
            indentOnInput: true,
            bracketMatching: true,
            closeBrackets: true,
            autocompletion: true,
            rectangularSelection: true,
            crosshairCursor: true,
            highlightActiveLine: true,
            highlightSelectionMatches: true,
            closeBracketsKeymap: true,
            defaultKeymap: true,
            searchKeymap: true,
            historyKeymap: true,
            foldKeymap: true,
            completionKeymap: true,
            lintKeymap: true,
          }}
        />
      </div>
    </div>
  );
}
