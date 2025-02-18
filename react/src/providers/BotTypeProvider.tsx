import { createContext, useContext, useState, ReactNode } from 'react';
import { BotType } from '../components/BotSelector';

type BotTypeContextType = {
  botType: BotType;
  setBotType: (type: BotType) => void;
};

const BotTypeContext = createContext<BotTypeContextType | undefined>(undefined);

export function BotTypeProvider({ children }: { children: ReactNode }) {
  const [botType, setBotType] = useState<BotType>('movie');

  return (
    <BotTypeContext.Provider value={{ botType, setBotType }}>
      {children}
    </BotTypeContext.Provider>
  );
}

export function useBotType() {
  const context = useContext(BotTypeContext);
  if (!context) {
    throw new Error('useBotType must be used within a BotTypeProvider');
  }
  return context;
} 