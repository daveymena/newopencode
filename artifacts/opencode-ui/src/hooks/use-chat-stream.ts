import { useState, useCallback, useRef } from 'react';
import type { Message } from '@workspace/api-client-react/src/generated/api.schemas';
import { useQueryClient } from '@tanstack/react-query';
import { getGetMessagesQueryKey } from '@workspace/api-client-react/src/generated/api';

interface ChatStreamRequest {
  sessionId: string;
  message: string;
  model: string;
  systemPrompt?: string;
}

export function useChatStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentStream, setCurrentStream] = useState<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const sendMessage = useCallback(async (req: ChatStreamRequest) => {
    setIsStreaming(true);
    setError(null);
    setCurrentStream('');
    
    abortControllerRef.current = new AbortController();

    // Optimistically add the user message to the cache
    const queryKey = getGetMessagesQueryKey(req.sessionId);
    queryClient.setQueryData(queryKey, (old: any) => {
      const userMessage: Message = {
        id: `temp-${Date.now()}`,
        sessionId: req.sessionId,
        role: 'user',
        content: req.message,
        createdAt: new Date().toISOString(),
      };
      return { messages: [...(old?.messages || []), userMessage] };
    });

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(req),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullResponseText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || ''; // Keep the last incomplete chunk in the buffer

        for (const part of parts) {
          if (part.startsWith('data: ')) {
            const dataStr = part.slice(6);
            if (dataStr === '[DONE]') continue;
            
            try {
              const data = JSON.parse(dataStr);
              if (data.content) {
                fullResponseText += data.content;
                setCurrentStream(fullResponseText);
              }
              if (data.done) {
                // Stream complete, the backend might send the final full message structure here 
                // but we rely on invalidating the query to get the persisted state
              }
            } catch (e) {
              console.error('Failed to parse SSE JSON:', e);
            }
          }
        }
      }

      // Once done, invalidate to fetch the actual persisted messages from DB
      queryClient.invalidateQueries({ queryKey });

    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Stream aborted');
      } else {
        setError(err.message || 'An error occurred during chat');
        console.error('Chat stream error:', err);
      }
    } finally {
      setIsStreaming(false);
      setCurrentStream('');
    }
  }, [queryClient]);

  const stopStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  return {
    sendMessage,
    stopStream,
    isStreaming,
    currentStream,
    error
  };
}
