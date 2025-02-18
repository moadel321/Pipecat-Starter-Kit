import { useEffect, useState } from "react";
import Vapi from "@vapi-ai/web";

const VAPI_PUBLIC_KEY = "your-public-key"; // Replace with your actual Vapi Public Key

const useVapi = () => {
  const [vapi, setVapi] = useState<Vapi | null>(null);
  const [volumeLevel, setVolumeLevel] = useState<number>(0);
  const [isSessionActive, setIsSessionActive] = useState<boolean>(false);

  useEffect(() => {
    // Initialize Vapi on mount
    const vapiInstance = new Vapi(VAPI_PUBLIC_KEY);
    setVapi(vapiInstance);

    // Listen for call events
    const startListener = () => setIsSessionActive(true);
    const endListener = () => setIsSessionActive(false);
    const volumeListener = (volume: number) => setVolumeLevel(volume);

    vapiInstance.on("call-start", startListener);
    vapiInstance.on("call-end", endListener);
    vapiInstance.on("volume-level", volumeListener);

    return () => {
      // Cleanup by removing event listeners
      if (vapiInstance) {
        vapiInstance.removeListener("call-start", startListener);
        vapiInstance.removeListener("call-end", endListener);
        vapiInstance.removeListener("volume-level", volumeListener);
      }
    };
  }, []);

  // Function to start/stop the Vapi call
  const toggleCall = async () => {
    if (!vapi) return;

    if (isSessionActive) {
      vapi.stop();
    } else {
      await vapi.start("your-assistant-id"); // Replace with your Vapi Assistant ID
    }
  };

  return { volumeLevel, isSessionActive, toggleCall };
};

export default useVapi; 