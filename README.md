# Pipecat Implementation Guide: Real-time Voice AI with React

This guide is complementary to the official [Pipecat documentation](https://docs.pipecat.ai). While the official docs cover the fundamentals, this guide focuses on practical implementation details, common pitfalls, and real-world optimization techniques.

## Quick Start

```bash
# Backend setup
cd bots
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
cp .env.example .env  # Then edit with your API keys

# Frontend setup
cd react
npm install
npm run dev
```

## Architecture Deep Dive

### Backend Pipeline Architecture

The backend uses a modular pipeline architecture for real-time audio processing:

```python
pipeline = [
    transport.input(),      # WebRTC input stream
    rtvi_speaking,         # Voice activity detection
    stt,                  # Speech-to-text conversion
    rtvi_user_transcript, # Real-time user transcript processing
    context_aggregator,   # Message context management
    llm,                 # Language model processing
    rtvi_bot_llm,       # Real-time LLM output processing
    tts,               # Text-to-speech conversion
    rtvi_bot_tts,    # Real-time TTS word streaming
    transport.output() # WebRTC output stream
]
```

Key insights:
- The pipeline is ordered for minimal latency
- Each processor runs in its own async task
- Frame processing is non-blocking
- Interruptions are handled gracefully

### Frontend Real-time Components

The React frontend uses a layered approach for real-time audio visualization and transcription:

```typescript
<RTVIProvider>              // WebRTC connection management
  <BotTypeProvider>         // Bot selection context
    <RadialCard />          // Audio visualization
    <Transcriber />         // Real-time transcription
    <RTVIClientAudio />     // Audio I/O management
  </BotTypeProvider>
</RTVIProvider>
```

## Performance Optimization

### Backend Optimizations

1. **Pipeline Buffering**
   - Keep buffer sizes small (≤100ms) for real-time responsiveness
   - Use ring buffers for audio processing to prevent memory growth
   ```python
   buffer_size = int(sample_rate * 0.1)  # 100ms buffer
   ```

2. **Voice Activity Detection**
   - Silero VAD is CPU-efficient but accurate
   - Pre-load model on startup to avoid runtime delays
   ```python
   vad_analyzer = SileroVADAnalyzer(
       threshold=0.5,  # Adjust based on environment noise
       min_speech_duration_ms=250,
       min_silence_duration_ms=100
   )
   ```

3. **Memory Management**
   - Clear message context periodically
   - Implement backpressure in the pipeline
   ```python
   if len(context.messages) > MAX_CONTEXT_LENGTH:
       context.messages = context.messages[-CONTEXT_WINDOW:]
   ```

### Frontend Optimizations

1. **Audio Visualization**
   - Use requestAnimationFrame for smooth rendering
   - Implement frequency band smoothing
   ```typescript
   const smoothingFactor = 0.4;
   bandValue = prevValue + (newValue - prevValue) * smoothingFactor;
   ```

2. **Transcript Rendering**
   - Virtualize long message lists
   - Debounce rapid updates
   ```typescript
   const debouncedUpdate = useDebounce(updateTranscript, 16);
   ```

## Common Pitfalls and Solutions

1. **WebRTC Connection Issues**
   ```typescript
   // Always handle disconnections gracefully
   useEffect(() => {
     const handleDisconnect = async () => {
       await cleanup();
       scheduleReconnect();
     };
     client.on('disconnected', handleDisconnect);
     return () => client.off('disconnected', handleDisconnect);
   }, []);
   ```

2. **Audio Context Initialization**
   ```typescript
   // Must be triggered by user interaction
   const initAudio = async () => {
     const audioContext = new AudioContext();
     await audioContext.resume();
   };
   ```

3. **Pipeline Backpressure**
   ```python
   # Implement backpressure to prevent memory issues
   async def process_frame(self, frame: Frame) -> Frame:
       if self.queue.qsize() > MAX_QUEUE_SIZE:
           logger.warning("Pipeline backpressure: dropping frame")
           return None
       return await self.queue.put(frame)
   ```

## Environment Setup

Required environment variables:
```bash
# API Keys
OPENAI_API_KEY=your_key_here
DAILY_API_KEY=your_key_here
DEEPGRAM_API_KEY=your_key_here
GLADIA_API_KEY=your_key_here

# Configuration
DAILY_ROOM_URL=your_room_url  # Optional, will create if not provided
FAST_API_PORT=7860
```

## Debugging Tools

1. **Pipeline Debugging**
   ```python
   logger.add("pipeline.log", 
              level="DEBUG",
              format="{time} | {level} | {message}",
              rotation="1 day")
   ```

2. **Frontend Debug Mode**
   ```typescript
   const DEBUG = process.env.NODE_ENV === 'development';
   if (DEBUG) {
     window.rtviClient = client;  // Expose for console debugging
   }
   ```

3. **WebRTC Statistics**
   ```typescript
   const getConnectionStats = async () => {
     const stats = await transport.getStats();
     console.table(stats);
   };
   ```

## Production Deployment

1. **Docker Setup**
   ```dockerfile
   # Multi-stage build for smaller image
   FROM python:3.11-slim as builder
   COPY requirements.txt .
   RUN pip install --user -r requirements.txt

   FROM python:3.11-slim
   COPY --from=builder /root/.local /root/.local
   COPY . .
   
   CMD ["python", "server.py"]
   ```

2. **Health Checks**
   ```python
   @app.get("/health")
   async def health_check():
       return {
           "status": "healthy",
           "pipeline_active": len(bot_procs) > 0,
           "memory_usage": psutil.Process().memory_info().rss / 1024 / 1024
       }
   ```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

BSD 2-Clause License - see LICENSE file for details

---

For more detailed information about specific components or advanced usage patterns, please refer to the official [Pipecat documentation](https://docs.pipecat.ai). 