import { useEffect, useState, useRef } from "react";
import { useRTVIClient, useRTVIClientTransportState, useRTVIClientMediaTrack } from "@pipecat-ai/client-react";

interface FrequencyBand {
  startFreq: number;
  endFreq: number;
  smoothValue: number;
}

const usePipecat = () => {
  const client = useRTVIClient();
  const transportState = useRTVIClientTransportState();
  const [volumeLevel, setVolumeLevel] = useState<number>(0);
  const [isSessionActive, setIsSessionActive] = useState<boolean>(false);
  const audioTrack = useRTVIClientMediaTrack("audio", "bot");
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animationFrameRef = useRef<number>();

  // Debug log for initial mount
  useEffect(() => {
    console.log('usePipecat Initial State:', {
      hasClient: !!client,
      transportState,
      hasAudioTrack: !!audioTrack,
      isSessionActive
    });
  }, []);

  const bandsRef = useRef<FrequencyBand[]>([
    { startFreq: 85, endFreq: 255, smoothValue: 0 },   // Fundamental frequencies
    { startFreq: 255, endFreq: 500, smoothValue: 0 },  // Lower formants
    { startFreq: 500, endFreq: 2000, smoothValue: 0 }, // Vowel formants
    { startFreq: 2000, endFreq: 4000, smoothValue: 0 }, // Higher formants
    { startFreq: 4000, endFreq: 8000, smoothValue: 0 }  // Sibilance
  ]);

  // Set session active based on transport state
  useEffect(() => {
    // Match the AudioVisualizer's behavior: consider active unless explicitly disconnected
    const newIsSessionActive = transportState !== 'disconnected';
    console.log('Session State Update:', {
      transportState,
      hasAudioTrack: !!audioTrack,
      currentlyActive: isSessionActive,
      willBeActive: newIsSessionActive,
      client: !!client
    });
    
    setIsSessionActive(newIsSessionActive);
  }, [transportState]);

  // Initialize audio analysis when track is available
  useEffect(() => {
    console.log('Audio Track Effect Triggered:', {
      hasTrack: !!audioTrack,
      transportState,
      isSessionActive
    });
    
    if (!audioTrack) {
      if (analyserRef.current) {
        console.log('Resetting volume level - no audio track');
        setVolumeLevel(0);
      }
      return;
    }

    console.log('Setting up audio analysis');
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(new MediaStream([audioTrack]));
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);
    analyserRef.current = analyser;
    console.log('Audio analysis setup complete');

    const frequencyData = new Uint8Array(analyser.frequencyBinCount);
    
    const getFrequencyBinIndex = (frequency: number) => {
      const nyquist = audioContext.sampleRate / 2;
      return Math.round((frequency / nyquist) * (analyser.frequencyBinCount - 1));
    };

    const updateLevel = () => {
      const currentAnalyser = analyserRef.current;
      if (!currentAnalyser) {
        console.log('No analyser available');
        return;
      }
      
      currentAnalyser.getByteFrequencyData(frequencyData);
      let totalEnergy = 0;
      const bands = bandsRef.current;
      const smoothingFactor = 0.4;

      bands.forEach(band => {
        const startIndex = getFrequencyBinIndex(band.startFreq);
        const endIndex = getFrequencyBinIndex(band.endFreq);
        const bandData = frequencyData.slice(startIndex, endIndex);
        const bandValue = bandData.reduce((acc, val) => acc + val, 0) / bandData.length;

        if (bandValue < 1) {
          band.smoothValue = Math.max(band.smoothValue - smoothingFactor * 5, 0);
        } else {
          band.smoothValue = band.smoothValue + (bandValue - band.smoothValue) * smoothingFactor;
        }

        totalEnergy += band.smoothValue;
      });

      const normalizedVolume = Math.min((totalEnergy / (bands.length * 255)) * 3, 1);
      if (normalizedVolume > 0.01) {  // Only log when there's significant volume
        // console.log('Volume Level:', normalizedVolume.toFixed(3), 'Session Active:', isSessionActive);
      }
      setVolumeLevel(normalizedVolume);
      
      animationFrameRef.current = requestAnimationFrame(updateLevel);
    };

    updateLevel();
    // console.log('Started audio level monitoring');

    return () => {
      // console.log('Cleaning up audio analysis');
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      audioContext.close();
      setVolumeLevel(0);
    };
  }, [audioTrack, isSessionActive]);

  return { volumeLevel, isSessionActive };
};

export default usePipecat; 