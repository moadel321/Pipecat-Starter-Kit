import { useCallback, useState } from 'react';
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
  const [currentBotWords, setCurrentBotWords] = useState<string[]>([]);

  // Handle user transcriptions
  const handleUserTranscript = useCallback((data: TranscriptData) => {
    console.log('User transcript:', data);
    const timestamp = new Date().toISOString();
    setMessages(prev => [...prev, {
      role: 'user',
      content: data.text,
      timestamp
    }]);
  }, []);

  // Handle bot TTS text streaming
  const handleBotTtsText = useCallback((data: BotLLMTextData) => {
    console.log('Bot TTS chunk:', data);
    setCurrentBotWords(prev => [...prev, data.text]);
  }, []);

  // Handle complete bot messages
  const handleBotTranscript = useCallback((data: BotLLMTextData) => {
    console.log('Bot transcript:', data);
    const timestamp = new Date().toISOString();
    setMessages(prev => [...prev, {
      role: 'assistant',
      content: data.text,
      timestamp
    }]);
    // Reset current bot words after complete message
    setCurrentBotWords([]);
  }, []);

  // Register event listeners
  useRTVIClientEvent(RTVIEvent.UserTranscript, handleUserTranscript);
  useRTVIClientEvent(RTVIEvent.BotTtsText, handleBotTtsText);
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
            {currentBotWords.length > 0 && (
              <div className="bot-message streaming">
                <p>{currentBotWords.join(' ')}</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}; 