import {
  RTVIClientAudio,
  RTVIClientVideo,
  useRTVIClientTransportState,
  VoiceVisualizer,
} from '@pipecat-ai/client-react';
import { RTVIProvider } from './providers/RTVIProvider';
import { BotTypeProvider } from './providers/BotTypeProvider';
import { ConnectButton } from './components/ConnectButton';
import { BotSelector } from './components/BotSelector';
import { StatusDisplay } from './components/StatusDisplay';
import { DebugDisplay } from './components/DebugDisplay';
import { Transcriber } from './components/Transcriber';
import RadialCard from './components/RadialCard';
import { TranscriptProvider } from './providers/TranscriptProvider';
import './App.css';


function BotAudioVisualizer() {
  const transportState = useRTVIClientTransportState();
  const isConnected = transportState !== 'disconnected';

  return (
    <div className="bot-container">
      <div className="visualizer-container">
        <RadialCard />
      </div>
    </div>
  );
}

function AppContent() {
  return (
    <div className="app">
      <div className="status-bar">
        <BotSelector />
        <ConnectButton />
      </div>

      <div className="main-content">
        <BotAudioVisualizer />
      </div>

      <DebugDisplay />
      <RTVIClientAudio />
    </div>
  );
}

function App() {
  return (
    <BotTypeProvider>
      <RTVIProvider>
        <TranscriptProvider>
          <AppContent />
        </TranscriptProvider>
      </RTVIProvider>
    </BotTypeProvider>
  );
}

export default App;
