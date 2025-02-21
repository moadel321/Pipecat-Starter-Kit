import { useCallback, useState, useEffect } from 'react';
import { useRTVIClientEvent } from '@pipecat-ai/client-react';
import { RTVIEvent, BotLLMTextData, TranscriptData } from '@pipecat-ai/client-js';
import './Transcriber.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export const Transcriber = () => {
  const [messages, setMessages] = useState<Message[]>([]);

  // Handle user transcriptions
  const handleUserTranscript = useCallback((data: TranscriptData) => {
    console.log('User transcript:', data);
    if (data.final) {
      const timestamp = new Date().toISOString();
      setMessages(prev => [...prev, {
        role: 'user',
        content: data.text,
        timestamp
      }]);
    }
  }, []);

  // Handle bot transcriptions
  const handleBotTranscript = useCallback((data: BotLLMTextData) => {
    console.log('Bot transcript:', data);
    if (data.text?.trim()) {
      const timestamp = new Date().toISOString();
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.text,
        timestamp
      }]);
    }
  }, []);

  // Debug logging for messages
  useEffect(() => {
    console.log('Current messages:', messages);
  }, [messages]);

  // Register event listeners
  useRTVIClientEvent(RTVIEvent.UserTranscript, handleUserTranscript);
  useRTVIClientEvent(RTVIEvent.BotTranscript, handleBotTranscript);

  return (
    <div className="w-full">
      <div className="p-4">
        <div className="transcriber-container">
          <div className="messages-container">
            {messages.map((message, index) => (
              <div 
                key={index} 
                className={`message ${message.role === 'user' ? 'user-message' : 'bot-message'}`}
              >
                <span className="timestamp">{new Date(message.timestamp).toLocaleTimeString()}</span>
                <p>{message.content}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}; 