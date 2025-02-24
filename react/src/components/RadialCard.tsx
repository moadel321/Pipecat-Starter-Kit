"use client";
import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Mic } from "lucide-react";
import usePipecat from "../hooks/usePipecat";

const RadialCard: React.FC = () => {
  const { volumeLevel, isSessionActive } = usePipecat();
  const [bars, setBars] = useState<number[]>(Array(50).fill(0));

  useEffect(() => {
    // console.log('RadialCard State:', { isSessionActive, volumeLevel });
    
    if (isSessionActive) {
      // console.log('Updating bars with volume:', volumeLevel);
      updateBars(volumeLevel);
    } else {
      // console.log('Resetting bars - session inactive');
      resetBars();
    }
  }, [volumeLevel, isSessionActive]);

  const updateBars = (volume: number) => {
    setBars((prevBars) => {
      const newBars = prevBars.map((_, index) => {
        const angleMultiplier = Math.sin((index / prevBars.length) * Math.PI * 2);
        
        // When volume is at maximum (close to 1), we want uniform length
        // Otherwise, keep the dynamic behavior with reduced variation
        if (volume > 0.9) {
          // When volume is very high, all bars extend to the same length (100)
          return 100;
        } else {
          // At lower volumes, maintain some variation but less pronounced
          const randomFactor = 1 + (Math.random() * 0.3); // Reduced randomness
          const amplifiedVolume = Math.min(volume * 4 * randomFactor, 1);
          const variationFactor = 0.8 + (Math.abs(angleMultiplier) * 0.2); // Less angle-based variation
          return amplifiedVolume * 100 * variationFactor;
        }
      });
      
      if (volume > 0.01) {  // Only log when there's significant volume
        // console.log('Bar heights (sample):', newBars.slice(0, 3).map(h => h.toFixed(1)));
      }
      return newBars;
    });
  };

  const resetBars = () => {
    // console.log('Resetting all bars to zero');
    setBars(Array(50).fill(0));
  };

  return (
    <div className="border text-center justify-items-center p-4 rounded-2xl overflow-hidden">
      <div
        className="flex items-center justify-center h-full relative overflow-hidden"
        style={{ 
          width: "300px", 
          height: "300px",
          overflowY: "hidden", /* Explicitly disable vertical scrollbar */
          overflowX: "hidden"  /* Explicitly disable horizontal scrollbar */
        }}
      >
        <motion.div
          animate={{
            scale: isSessionActive && volumeLevel > 0.1 ? [1, 1.05, 1] : 1,
            transition: { duration: 0.5 }
          }}
        >
          <Mic
            size={28}
            className={`text-black dark:text-white ${isSessionActive ? 'opacity-100' : 'opacity-50'}`}
          />
        </motion.div>
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 300 300"
          style={{ 
            position: "absolute", 
            top: 0, 
            left: 0,
            overflow: "visible" /* Ensure SVG content is visible but doesn't cause scrollbars */
          }}
        >
          {bars.map((height, index) => {
            const angle = (index / bars.length) * 360;
            const radians = (angle * Math.PI) / 180;
            const x1 = 150 + Math.cos(radians) * 50;
            const y1 = 150 + Math.sin(radians) * 50;
            const x2 = 150 + Math.cos(radians) * (100 + height);
            const y2 = 150 + Math.sin(radians) * (100 + height);

            return (
              <motion.line
                key={index}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                className="stroke-current text-black dark:text-white dark:opacity-70 opacity-70"
                strokeWidth="2"
                initial={{ x2: x1, y2: y1 }}
                animate={{ x2, y2 }}
                transition={{ 
                  type: "spring",
                  stiffness: 500,
                  damping: 8,
                  mass: 0.3
                }}
              />
            );
          })}
        </svg>
        <motion.span 
          className="absolute top-48 w-[calc(100%-70%)] h-[calc(100%-70%)] bg-primary blur-[120px]"
          animate={{
            opacity: isSessionActive ? [0.4, 0.6, 0.4] : 0.2,
            scale: isSessionActive && volumeLevel > 0.1 ? [1, 1.15, 1] : 1,
          }}
          transition={{
            duration: 0.5,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        />
      </div>
    </div>
  );
};

export default RadialCard;
