import { createContext, useContext, useState, ReactNode } from 'react';
import { TranscriptData, BotLLMTextData } from '@pipecat-ai/client-js';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isComplete: boolean;
}

interface TranscriptContextType {
  messages: Message[];
  addUserMessage: (data: TranscriptData) => void;
  addBotMessage: (text: string) => void;
  updateLastBotMessage: (text: string) => void;
  markLastBotMessageComplete: () => void;
}

const TranscriptContext = createContext<TranscriptContextType | undefined>(undefined);

export function TranscriptProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);

  const addUserMessage = (data: TranscriptData) => {
    if (data.final) {
      const timestamp = new Date().toISOString();
      setMessages(prev => [...prev, {
        role: 'user',
        content: data.text,
        timestamp,
        isComplete: true
      }]);
    }
  };

  const addBotMessage = (text: string) => {
    const timestamp = new Date().toISOString();
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: text,
      timestamp,
      isComplete: false
    }]);
  };

  const updateLastBotMessage = (text: string) => {
    setMessages(prev => {
      const lastMessage = prev[prev.length - 1];
      if (lastMessage?.role === 'assistant' && !lastMessage.isComplete) {
        const updatedMessages = [...prev];
        updatedMessages[prev.length - 1] = {
          ...lastMessage,
          content: text
        };
        return updatedMessages;
      }
      return prev;
    });
  };

  const markLastBotMessageComplete = () => {
    setMessages(prev => {
      const updatedMessages = [...prev];
      if (updatedMessages.length > 0) {
        const lastMessage = updatedMessages[updatedMessages.length - 1];
        if (lastMessage.role === 'assistant') {
          updatedMessages[updatedMessages.length - 1] = {
            ...lastMessage,
            isComplete: true
          };
        }
      }
      return updatedMessages;
    });
  };

  return (
    <TranscriptContext.Provider value={{
      messages,
      addUserMessage,
      addBotMessage,
      updateLastBotMessage,
      markLastBotMessageComplete
    }}>
      {children}
    </TranscriptContext.Provider>
  );
}

export function useTranscript() {
  const context = useContext(TranscriptContext);
  if (!context) {
    throw new Error('useTranscript must be used within a TranscriptProvider');
  }
  return context;
} 