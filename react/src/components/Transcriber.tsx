import { useCallback, useRef, useEffect } from 'react';
import { useRTVIClientEvent } from '@pipecat-ai/client-react';
import { RTVIEvent, TranscriptData, BotLLMTextData } from '@pipecat-ai/client-js';
import { useTranscript } from '../providers/TranscriptProvider';
import './Transcriber.css';

export const Transcriber = () => {
  const { messages, addUserMessage, addBotMessage, updateLastBotMessage, markLastBotMessageComplete } = useTranscript();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentBotWordsRef = useRef<string[]>([]);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Handle user transcriptions
  const handleUserTranscript = useCallback((data: TranscriptData) => {
    console.log('User transcript:', data);
    addUserMessage(data);
  }, [addUserMessage]);

  // Handle start of bot response
  const handleBotLLMStarted = useCallback(() => {
    console.log('Bot LLM started');
    currentBotWordsRef.current = [];
  }, []);

  // Handle bot LLM text chunks
  const handleBotLLMText = useCallback((data: BotLLMTextData) => {
    console.log('Bot LLM text:', data);
    if (data.text?.trim()) {
      currentBotWordsRef.current = [...currentBotWordsRef.current, data.text];
      
      const lastMessage = messages[messages.length - 1];
      if (lastMessage?.role === 'assistant' && !lastMessage.isComplete) {
        updateLastBotMessage(currentBotWordsRef.current.join(' '));
      } else {
        addBotMessage(data.text);
      }
    }
  }, [messages, addBotMessage, updateLastBotMessage]);

  // Handle end of bot response
  const handleBotLLMStopped = useCallback(() => {
    console.log('Bot LLM stopped');
    markLastBotMessageComplete();
    currentBotWordsRef.current = [];
  }, [markLastBotMessageComplete]);

  // Register event listeners
  useRTVIClientEvent(RTVIEvent.UserTranscript, handleUserTranscript);
  useRTVIClientEvent(RTVIEvent.BotLlmStarted, handleBotLLMStarted);
  useRTVIClientEvent(RTVIEvent.BotLlmText, handleBotLLMText);
  useRTVIClientEvent(RTVIEvent.BotLlmStopped, handleBotLLMStopped);

  return (
    <div className="w-full">
      <div className="transcript-container">
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
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>
    </div>
  );
}; 