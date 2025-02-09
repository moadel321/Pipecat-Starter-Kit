import { type PropsWithChildren, useEffect } from 'react';
import { RTVIClient } from '@pipecat-ai/client-js';
import { DailyTransport } from '@pipecat-ai/daily-transport';
import { RTVIClientProvider } from '@pipecat-ai/client-react';

// Create transport with debug logging
const transport = new DailyTransport({
  dailyConfig: {
    subscribeToTracksAutomatically: true,
    audioSource: true,
    videoSource: false,
    // Add debugging
    logLevel: 'debug',
  },
});

// Create RTVI client with the transport
const client = new RTVIClient({
  transport,
  params: {
    baseUrl: 'http://49.13.226.238:7860',
    endpoints: {
      connect: '/connect',
      status: '/status',
      health: '/health',
    }
  },
  enableMic: true,
  // Add debug logging for the client
  debug: true,
});

export function RTVIProvider({ children }: PropsWithChildren) {
  useEffect(() => {
    // Log initial setup
    console.log('[RTVIProvider] Initializing with config:', {
      baseUrl: client.params.baseUrl,
      endpoints: client.params.endpoints,
    });

    // Add health check
    const checkHealth = async () => {
      try {
        const response = await fetch(`${client.params.baseUrl}/health`);
        const data = await response.json();
        console.log('[RTVIProvider] Health check response:', data);
      } catch (error) {
        console.error('[RTVIProvider] Health check failed:', error);
      }
    };

    // Setup client event listeners
    const onClientStateChange = (state: any) => {
      console.log('[RTVI Client] State changed:', state);
    };

    const onClientError = (error: any) => {
      console.error('[RTVI Client] Error:', error);
    };

    // Add listeners
    client.on('stateChanged', onClientStateChange);
    client.on('error', onClientError);

    // Run health check
    checkHealth();

    // Cleanup listeners on unmount
    return () => {
      client.off('stateChanged', onClientStateChange);
      client.off('error', onClientError);
    };
  }, []);

  return (
    <RTVIClientProvider client={client}>
      {children}
    </RTVIClientProvider>
  );
}
