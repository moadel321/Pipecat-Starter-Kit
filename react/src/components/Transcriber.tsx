import { useCallback, useState, useEffect } from 'react';
import { useRTVIClientEvent } from '@pipecat-ai/client-react';
import { RTVIEvent, TranscriptData, BotLLMTextData } from '@pipecat-ai/client-js';
import './Transcriber.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isComplete: boolean;
}

export const Transcriber = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLLMStreaming, setIsLLMStreaming] = useState(false);
  const [currentBotWords, setCurrentBotWords] = useState<string[]>([]);

  // Handle user transcriptions
  const handleUserTranscript = useCallback((data: TranscriptData) => {
    console.log('User transcript:', data);
    if (data.final) {
      const timestamp = new Date().toISOString();
      setMessages(prev => [...prev, {
        role: 'user',
        content: data.text,
        timestamp,
        isComplete: true
      }]);
    }
  }, []);

  // Handle start of bot response
  const handleBotLLMStarted = useCallback(() => {
    console.log('Bot LLM started');
    setIsLLMStreaming(true);
    setCurrentBotWords([]);
  }, []);

  // Handle bot LLM text chunks
  const handleBotLLMText = useCallback((data: BotLLMTextData) => {
    console.log('Bot LLM text:', data);
    if (data.text?.trim()) {
      setCurrentBotWords(prev => [...prev, data.text]);
      
      // Update the current streaming message or create a new one
      setMessages(prev => {
        const timestamp = new Date().toISOString();
        const lastMessage = prev[prev.length - 1];
        
        if (lastMessage?.role === 'assistant' && !lastMessage.isComplete) {
          // Update existing streaming message
          const updatedMessages = [...prev];
          updatedMessages[prev.length - 1] = {
            ...lastMessage,
            content: [...currentBotWords, data.text].join(' ')
          };
          return updatedMessages;
        } else {
          // Create new streaming message
          return [...prev, {
            role: 'assistant',
            content: data.text,
            timestamp,
            isComplete: false
          }];
        }
      });
    }
  }, [currentBotWords]);

  // Handle end of bot response
  const handleBotLLMStopped = useCallback(() => {
    console.log('Bot LLM stopped');
    setIsLLMStreaming(false);
    
    // Mark the last message as complete
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
    
    // Clear streaming buffer
    setCurrentBotWords([]);
  }, []);

  // Debug logging for messages
  useEffect(() => {
    console.log('Current messages:', messages);
    console.log('Is streaming:', isLLMStreaming);
    console.log('Current bot words:', currentBotWords);
  }, [messages, isLLMStreaming, currentBotWords]);

  // Register event listeners
  useRTVIClientEvent(RTVIEvent.UserTranscript, handleUserTranscript);
  useRTVIClientEvent(RTVIEvent.BotLlmStarted, handleBotLLMStarted);
  useRTVIClientEvent(RTVIEvent.BotLlmText, handleBotLLMText);
  useRTVIClientEvent(RTVIEvent.BotLlmStopped, handleBotLLMStopped);

  return (
    <div className="w-full">
      <div className="p-4">
        <div className="transcriber-container">
          <div className="messages-container">
            {messages.map((message, index) => (
              <div 
                key={index} 
                className={`message ${message.role === 'user' ? 'user-message' : 'bot-message'} ${!message.isComplete ? 'streaming' : ''}`}
              >
                <span className="timestamp">{new Date(message.timestamp).toLocaleTimeString()}</span>
                <p>{message.content}</p>
                {!message.isComplete && <span className="streaming-indicator">...</span>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}; 