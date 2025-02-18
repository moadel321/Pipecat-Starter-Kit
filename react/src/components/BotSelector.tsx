import { useCallback } from 'react';
import { useBotType } from '../providers/BotTypeProvider';

export type BotType = 'movie' | 'intake' | 'cv';

export function BotSelector() {
  const { botType, setBotType } = useBotType();
  
  const handleBotChange = useCallback((event: React.ChangeEvent<HTMLSelectElement>) => {
    const newBotType = event.target.value as BotType;
    setBotType(newBotType);
  }, [setBotType]);

  return (
    <div className="bot-selector">
      <select onChange={handleBotChange} value={botType}>
      <option value="movie">Movie Explorer Bot</option>
      <option value="intake">Patient Intake Bot</option>
      </select>
    </div>
  );
} 