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
  const [currentBotWords, setCurrentBotWords] = useState<string[]>([]);
  const [isLLMStreaming, setIsLLMStreaming] = useState(false);

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

  // Handle bot LLM streaming text
  const handleBotLLMText = useCallback((data: BotLLMTextData) => {
    console.log('Bot LLM text:', data);
    if (isLLMStreaming) {
      setCurrentBotWords(prev => [...prev, data.text]);
    }
  }, [isLLMStreaming]);

  // Handle LLM start
  const handleBotLLMStart = useCallback(() => {
    console.log('Bot LLM started');
    setIsLLMStreaming(true);
    setCurrentBotWords([]);
  }, []);

  // Handle LLM stop
  const handleBotLLMStop = useCallback(() => {
    console.log('Bot LLM stopped');
    setIsLLMStreaming(false);
    // Add the complete message to the messages list
    if (currentBotWords.length > 0) {
      const timestamp = new Date().toISOString();
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: currentBotWords.join(' '),
        timestamp
      }]);
      setCurrentBotWords([]);
    }
  }, [currentBotWords]);

  // Handle TTS text streaming
  const handleBotTTSText = useCallback((data: BotLLMTextData) => {
    console.log('Bot TTS text:', data);
  }, []);

  // Debug logging for messages and events
  useEffect(() => {
    console.log('Current messages:', messages);
  }, [messages]);

  // Register event listeners
  useRTVIClientEvent(RTVIEvent.UserTranscript, handleUserTranscript);
  useRTVIClientEvent(RTVIEvent.BotLlmStarted, handleBotLLMStart);
  useRTVIClientEvent(RTVIEvent.BotLlmStopped, handleBotLLMStop);
  useRTVIClientEvent(RTVIEvent.BotLlmText, handleBotLLMText);
  useRTVIClientEvent(RTVIEvent.BotTtsText, handleBotTTSText);

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