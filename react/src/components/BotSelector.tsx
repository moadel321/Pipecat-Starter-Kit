import { useCallback } from 'react';
import { useBotType } from '../providers/BotTypeProvider';

export type BotType = 'intake' | 'movie';

export function BotSelector() {
  const { botType, setBotType } = useBotType();
  
  const handleBotChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    const newBotType = event.target.value as BotType;
    setBotType(newBotType);
  }, [setBotType]);

  return (
    <div className="bot-selector">
      <select onChange={handleBotChange} value={botType}>
        <option value="intake">Patient Intake Bot</option>
        <option value="movie">Movie Explorer Bot</option>
      </select>
    </div>
  );
} 