import { useCallback, useState } from 'react';
import {
  useRTVIClient,
  useRTVIClientTransportState,
} from '@pipecat-ai/client-react';
import { useBotType } from '../providers/BotTypeProvider';

export function ConnectButton() {
  const client = useRTVIClient();
  const transportState = useRTVIClientTransportState();
  const { botType } = useBotType();
  const [error, setError] = useState<string | null>(null);

  const handleConnect = useCallback(async () => {
    if (!client) {
      setError('RTVIClient not initialized');
      return;
    }

    try {
      console.log('[ConnectButton] Attempting to connect...');
      setError(null);
      
      // Set parameters in requestData as per SDK spec
      client.params.requestData = { botType };
      
      await client.connect();
      console.log('[ConnectButton] Connection successful');
    } catch (err) {
      console.error('[ConnectButton] Connection error:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    }
  }, [client, botType]);

  const handleDisconnect = useCallback(async () => {
    if (!client) {
      setError('RTVIClient not initialized');
      return;
    }

    try {
      console.log('[ConnectButton] Attempting to disconnect...');
      await client.disconnect();
      console.log('[ConnectButton] Disconnection successful');
      setError(null);
    } catch (err) {
      console.error('[ConnectButton] Disconnection error:', err);
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
    }
  }, [client]);

  const isConnected = transportState === 'connected';

  return (
    <div className="connect-button-container">
      <button 
        onClick={isConnected ? handleDisconnect : handleConnect}
        disabled={transportState === 'connecting' || transportState === 'authenticating'}
      >
        {transportState === 'connecting' || transportState === 'authenticating' 
          ? 'Connecting...' 
          : isConnected 
            ? 'Disconnect' 
            : 'Connect'}
      </button>
      {error && <div className="error-message">Error: {error}</div>}
      <div className="status-message">Transport State: {transportState}</div>
    </div>
  );
}
