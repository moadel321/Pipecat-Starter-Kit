# Pipecat Starter Kit: Real-time Voice AI with Pipecat

Welcome to the Pipecat Starter Kit! This repository is designed to help you quickly get started with the Pipecat Framework, providing a comprehensive boilerplate for building real-time voice AI applications. Whether you're new to Pipecat or looking to streamline your development process, this starter kit has you covered.

## Overview

Pipecat can be complex for newcomers, but this starter kit simplifies the process by integrating essential features and services into a single package. Here's what you'll find:

- **Sentry for Metrics Logging**: Monitor and log application metrics seamlessly.
- **Transcription Streaming**: Real-time transcription streaming to the frontend.
- **Back-Channeling**: Enhance conversational flow with back-channeling capabilities.
- **Function Calling**: Execute functions dynamically within the conversation.
- **Multilingual Support**: Engage users in multiple languages.
- **Vapi Compoenents**: Extra rizz


The backend leverages Pipecat Flows for  conversation management, while the frontend is built using the Pipecat React SDK.

## Quick Start

Follow these steps to set up your environment and start developing:

### Backend Setup

```bash
cd bots
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys

# Start the server using UV
uv run python server.py
```

### Frontend Setup

```bash
cd react
npm install
npm run dev
```

## Architecture

### Backend

The backend is structured around a modular pipeline architecture, ensuring minimal latency and efficient processing:

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

### Frontend

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


## Environment Setup

Ensure you have the following environment variables configured:

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

## **Additional Environment Variables**

Depending on the bot type you're using, you may need to configure these additional variables:


## Debugging Tools

- **Pipeline Debugging**: Log pipeline activities for troubleshooting.
- **Sentry  Statistics**: Monitor WebRTC connection stats.

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## License

This project is licensed under the BSD 2-Clause License. See the LICENSE file for details.

---

For more detailed information about specific components or advanced usage patterns, please refer to the official [Pipecat documentation](https://docs.pipecat.ai).

