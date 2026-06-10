import { useState } from 'react';
import { ChevronRight, ChevronDown, FileCode, Folder, FolderOpen, RefreshCcw } from 'lucide-react';
import { useListFiles, getListFilesQueryKey } from '@workspace/api-client-react/src/generated/api';
import type { FileNode } from '@workspace/api-client-react/src/generated/api.schemas';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
import { useQueryClient } from '@tanstack/react-query';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface FileExplorerProps {
  onFileSelect: (path: string) => void;
  activeFile: string | null;
}

function TreeNode({ node, depth, onSelect, activeFile }: { node: FileNode, depth: number, onSelect: (path: string) => void, activeFile: string | null }) {
  const [isOpen, setIsOpen] = useState(depth < 1);
  const isDir = node.type === 'directory';
  const isActive = activeFile === node.path;

  const handleClick = () => {
    if (isDir) {
      setIsOpen(!isOpen);
    } else {
      onSelect(node.path);
    }
  };

  return (
    <div>
      <div 
        className={cn(
          "flex items-center py-1.5 px-2 cursor-pointer transition-colors text-sm group select-none",
          isActive ? "bg-primary/20 text-primary font-medium" : "text-muted-foreground hover:bg-muted/50 hover:text-foreground",
        )}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
        onClick={handleClick}
      >
        <div className="w-4 h-4 mr-1.5 flex items-center justify-center shrink-0">
          {isDir ? (
            isOpen ? <ChevronDown className="w-3.5 h-3.5 opacity-70" /> : <ChevronRight className="w-3.5 h-3.5 opacity-70" />
          ) : (
             <FileCode className={cn("w-3.5 h-3.5", isActive ? "text-primary" : "opacity-60")} />
          )}
        </div>
        {isDir && (
          <div className="mr-2">
            {isOpen ? <FolderOpen className="w-4 h-4 text-accent-foreground/70" /> : <Folder className="w-4 h-4 text-accent-foreground/70" />}
          </div>
        )}
        <span className="truncate">{node.name}</span>
      </div>
      
      {isDir && isOpen && node.children && (
        <div className="flex flex-col">
          {node.children.map((child, i) => (
            <TreeNode 
              key={`${child.path}-${i}`} 
              node={child} 
              depth={depth + 1} 
              onSelect={onSelect}
              activeFile={activeFile}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function FileExplorer({ onFileSelect, activeFile }: FileExplorerProps) {
  const { data, isLoading, error } = useListFiles({ path: '.' });
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: getListFilesQueryKey() });
  };

  return (
    <div className="flex flex-col h-full bg-card border-r border-border">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">Explorer</h2>
        <button onClick={handleRefresh} className="p-1 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors" title="Refresh">
          <RefreshCcw className="w-3.5 h-3.5" />
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto py-2">
        {isLoading && (
          <div className="flex flex-col items-center justify-center h-32 text-muted-foreground">
            <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin mb-2" />
            <span className="text-xs">Loading workspace...</span>
          </div>
        )}
        
        {error && (
          <div className="p-4 text-sm text-destructive text-center">
            Failed to load files. Check connection.
          </div>
        )}
        
        {data?.tree && (
          <TreeNode 
            node={data.tree} 
            depth={0} 
            onSelect={onFileSelect} 
            activeFile={activeFile}
          />
        )}
      </div>
    </div>
  );
}
