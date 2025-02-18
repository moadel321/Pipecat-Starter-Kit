import { useRef, useCallback } from 'react';
import {
  Participant,
  RTVIEvent,
  TransportState,
  TranscriptData,
  BotLLMTextData,
} from '@pipecat-ai/client-js';
import { useRTVIClient, useRTVIClientEvent, useRTVIClientTransportState, useRTVIClientMediaTrack } from '@pipecat-ai/client-react';
import './DebugDisplay.css';
import { useState } from 'react';
import { Tab } from '@headlessui/react';
import { cn } from '../lib/utils';
import { Transcriber } from './Transcriber';

function DebugInfo() {
  const transportState = useRTVIClientTransportState();
  const audioTrack = useRTVIClientMediaTrack('audio', 'bot');
  const videoTrack = useRTVIClientMediaTrack('video', 'bot');

  return (
    <div className="space-y-4 text-black dark:text-white">
      <div>Transport State: {transportState}</div>
      <div>Audio Track: {audioTrack ? 'Yes' : 'No'}</div>
      <div>Video Track: {videoTrack ? 'Yes' : 'No'}</div>
    </div>
  );
}

export function DebugDisplay() {
  const [selectedTab, setSelectedTab] = useState(0);
  
  return (
    <div className="fixed bottom-4 right-4 left-4 bg-white dark:bg-gray-800 rounded-lg shadow-lg">
      <Tab.Group selectedIndex={selectedTab} onChange={setSelectedTab}>
        <Tab.List className="flex w-full border-b border-gray-200 dark:border-gray-700">
          <Tab className={({ selected }) => cn(
            'w-full py-3 text-sm font-medium transition-colors',
            'focus:outline-none hover:text-blue-600 dark:hover:text-blue-400',
            selected 
              ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400' 
              : 'text-gray-500 dark:text-gray-400'
          )}>
            Debug Info
          </Tab>
          <Tab className={({ selected }) => cn(
            'w-full py-3 text-sm font-medium transition-colors',
            'focus:outline-none hover:text-blue-600 dark:hover:text-blue-400',
            selected 
              ? 'text-blue-600 dark:text-blue-400 border-b-2 border-blue-600 dark:border-blue-400' 
              : 'text-gray-500 dark:text-gray-400'
          )}>
            Transcription
          </Tab>
        </Tab.List>
        <Tab.Panels className="p-4">
          <Tab.Panel>
            <DebugInfo />
          </Tab.Panel>
          <Tab.Panel>
            <Transcriber />
          </Tab.Panel>
        </Tab.Panels>
      </Tab.Group>
    </div>
  );
}
