import { useEffect, useState } from 'react';
import { useRTVIClient, useRTVIClientTransportState } from '@pipecat-ai/client-react';

export function StatusDisplay() {
  const client = useRTVIClient();
  const transportState = useRTVIClientTransportState();
  const [botStatus, setBotStatus] = useState<string>('');

  useEffect(() => {
    const checkStatus = async () => {
      if (client && transportState === 'connected') {
        try {
          const response = await fetch(`${client.params.baseUrl}/status/${client.botPid}`);
          const data = await response.json();
          setBotStatus(data.status);
        } catch (error) {
          console.error('Status check failed:', error);
        }
      }
    };

    const interval = setInterval(checkStatus, 5000); // Check every 5 seconds
    return () => clearInterval(interval);
  }, [client, transportState]);

  return (
    <div className="status">
      <span>Transport: {transportState}</span>
      {botStatus && <span> | Bot: {botStatus}</span>}
    </div>
  );
}
