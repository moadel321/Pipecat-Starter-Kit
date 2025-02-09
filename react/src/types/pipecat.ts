import type { RTVIClient } from '@pipecat-ai/client-js';

declare module '@pipecat-ai/client-js' {
  interface RTVIClient {
    connect(params?: Record<string, any>): Promise<void>;
  }
} 