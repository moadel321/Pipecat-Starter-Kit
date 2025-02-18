#
# Copyright (c) 2024, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

from typing import AsyncGenerator, Literal, Optional

from elevenlabs.client import AsyncElevenLabs
from loguru import logger
from pipecat.frames.frames import (
    Frame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.services.ai_services import WordTTSService
from pipecat.transcriptions.language import Language
from pydantic import BaseModel, model_validator


ElevenLabsOutputFormat = Literal["pcm_16000", "pcm_22050", "pcm_24000", "pcm_44100"]


def language_to_elevenlabs_language(language: Language) -> str | None:
    BASE_LANGUAGES = {
        Language.AR: "ar",
        Language.BG: "bg",
        Language.CS: "cs",
        Language.DA: "da",
        Language.DE: "de",
        Language.EL: "el",
        Language.EN: "en",
        Language.ES: "es",
        Language.FI: "fi",
        Language.FIL: "fil",
        Language.FR: "fr",
        Language.HI: "hi",
        Language.HR: "hr",
        Language.HU: "hu",
        Language.ID: "id",
        Language.IT: "it",
        Language.JA: "ja",
        Language.KO: "ko",
        Language.MS: "ms",
        Language.NL: "nl",
        Language.NO: "no",
        Language.PL: "pl",
        Language.PT: "pt",
        Language.RO: "ro",
        Language.RU: "ru",
        Language.SK: "sk",
        Language.SV: "sv",
        Language.TA: "ta",
        Language.TR: "tr",
        Language.UK: "uk",
        Language.VI: "vi",
        Language.ZH: "zh",
    }

    result = BASE_LANGUAGES.get(language)

    # If not found in base languages, try to find the base language from a variant
    if not result:
        # Convert enum value to string and get the base language part (e.g. es-ES -> es)
        lang_str = str(language.value)
        base_code = lang_str.split("-")[0].lower()
        # Look up the base code in our supported languages
        result = base_code if base_code in BASE_LANGUAGES.values() else None

    return result


def sample_rate_from_output_format(output_format: str) -> int:
    match output_format:
        case "pcm_16000":
            return 16000
        case "pcm_22050":
            return 22050
        case "pcm_24000":
            return 24000
        case "pcm_44100":
            return 44100
    return 16000


class VoxaElevenLabsTTS(WordTTSService):
    class InputParams(BaseModel):
        language: Optional[Language] = Language.EN
        optimize_streaming_latency: Optional[str] = None
        stability: Optional[float] = None
        similarity_boost: Optional[float] = None
        style: Optional[float] = None
        use_speaker_boost: Optional[bool] = None

        @model_validator(mode="after")
        def validate_voice_settings(self):
            stability = self.stability
            similarity_boost = self.similarity_boost
            if (stability is None) != (similarity_boost is None):
                raise ValueError(
                    "Both 'stability' and 'similarity_boost' must be provided when using voice settings",
                )
            return self

    def __init__(
        self,
        *,
        api_key: str,
        voice_id: str,
        model: str = "eleven_turbo_v2_5",
        url: str = "https://api.elevenlabs.io",
        output_format: ElevenLabsOutputFormat = "pcm_24000",
        params: InputParams = InputParams(),
        **kwargs,
    ):
        # Initialize with streaming params
        super().__init__(
            aggregate_sentences=True,
            push_text_frames=False,
            push_stop_frames=True,
            stop_frame_timeout_s=2.0,
            sample_rate=sample_rate_from_output_format(output_format),
            **kwargs,
        )

        self._api_key = api_key
        self._url = url
        self._settings = {
            "sample_rate": sample_rate_from_output_format(output_format),
            "language": self.language_to_service_language(params.language)
            if params.language
            else "en",
            "output_format": output_format,
            "optimize_streaming_latency": params.optimize_streaming_latency,
            "stability": params.stability,
            "similarity_boost": params.similarity_boost,
            "style": params.style,
            "use_speaker_boost": params.use_speaker_boost,
        }
        self.set_model_name(model)
        self.set_voice(voice_id)
        self._voice_settings = self._set_voice_settings()
        self._started = False
        self._cumulative_time = 0

    def can_generate_metrics(self) -> bool:
        return True

    def language_to_service_language(self, language: Language) -> str | None:
        return language_to_elevenlabs_language(language)

    def _set_voice_settings(self):
        voice_settings = {}
        if (
            self._settings["stability"] is not None
            and self._settings["similarity_boost"] is not None
        ):
            voice_settings["stability"] = self._settings["stability"]
            voice_settings["similarity_boost"] = self._settings["similarity_boost"]
            if self._settings["style"] is not None:
                voice_settings["style"] = self._settings["style"]
            if self._settings["use_speaker_boost"] is not None:
                voice_settings["use_speaker_boost"] = self._settings[
                    "use_speaker_boost"
                ]
        else:
            if self._settings["style"] is not None:
                logger.warning(
                    "'style' is set but will not be applied because 'stability' and 'similarity_boost' are not both set.",
                )
            if self._settings["use_speaker_boost"] is not None:
                logger.warning(
                    "'use_speaker_boost' is set but will not be applied because 'stability' and 'similarity_boost' are not both set.",
                )

        return voice_settings or None

    async def set_model(self, model: str):
        await super().set_model(model)
        logger.info(f"Switching TTS model to: [{model}]")

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        logger.debug(f"Generating TTS: [{text}]")

        # Initialize async client
        client = AsyncElevenLabs(api_key=self._api_key)

        # Get audio without streaming
        audio = await client.generate(
            text=text,
            voice=self._voice_id,
            model=self.model_name,
            # output_format="mp3",
            output_format="pcm_24000",
            voice_settings=self._voice_settings,
        )

        yield TTSStartedFrame()

        out = b""
        async for value in audio:
            out += value

        frame = TTSAudioRawFrame(out, self._settings["sample_rate"], 1)
        yield frame

        yield TTSStoppedFrame()
