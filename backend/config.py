"""Single tunable home for thresholds, weights, and model assignments.

Nothing in agents/, graph/, or services/ should hardcode a number that
appears here. During a demo rehearsal, this is the one file worth opening.
See HACKATHON_PLAN.md sections 5.2, 6, 10.1, and 17.3 for the rationale
behind each constant.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    val = os.getenv(name)
    return float(val) if val else default


# ---------------------------------------------------------------------------
# Model assignment (plan section 17.3)
# ---------------------------------------------------------------------------

DEMO_FAST_MODE = _env_bool("DEMO_FAST_MODE", False)

_MODEL_FULL = {
    "normalization": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "memory_relevance": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "rag_rerank": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "analyst": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "guardrail": "openai/gpt-oss-safeguard-20b",
    "stress_test": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "report_writer": "nvidia/nemotron-3.5-lightning-30b-a3b",
}

# DEMO_FAST_MODE downgrades every task to cheaper/faster workhorse models.
_MODEL_FAST = {
    "normalization": "openai/gpt-oss-20b",
    "memory_relevance": "openai/gpt-oss-20b",
    "rag_rerank": "openai/gpt-oss-20b",
    "analyst": "openai/gpt-oss-120b",
    "guardrail": "openai/gpt-oss-safeguard-20b",
    "stress_test": "openai/gpt-oss-20b",
    "report_writer": "openai/gpt-oss-120b",
}

MODELS: dict[str, str] = _MODEL_FAST if DEMO_FAST_MODE else dict(_MODEL_FULL)


# ---------------------------------------------------------------------------
# LLM client behavior
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

LLM_ROUTES = {
    # Fast structuring / cleanup work: cheap and low-latency.
    "normalization": {
        "provider": os.getenv("LLM_PROVIDER_NORMALIZATION", "groq"),
        "model": os.getenv("LLM_MODEL_NORMALIZATION", "openai/gpt-oss-20b"),
    },
    # Memory and RAG are lower-risk, high-frequency calls, so place them on
    # OpenRouter's free pool to preserve Groq/NVIDIA quota for heavier agents.
    "memory_relevance": {
        "provider": os.getenv("LLM_PROVIDER_MEMORY_RELEVANCE", "openrouter"),
        "model": os.getenv("LLM_MODEL_MEMORY_RELEVANCE", "nvidia/nemotron-3.5-lightning:free"),
    },
    "rag_rerank": {
        "provider": os.getenv("LLM_PROVIDER_RAG_RERANK", "openrouter"),
        "model": os.getenv("LLM_MODEL_RAG_RERANK", "nvidia/nemotron-3.5-lightning:free"),
    },
    # The main CFO explanation should showcase the NVIDIA sponsor model.
    # Two constraints pick the model:
    #   - nemotron-3-super-120b-a12b is in NVIDIA's public catalog but returns
    #     404 "Not found for account" on this key, so it fails every run.
    #   - nemotron-3-ultra-550b-a55b is enabled and gives the best answer, but
    #     the guardrail can send the analyst back twice (MAX_REVISION_PASSES),
    #     and three sequential 550B calls overran the frontend's poll timeout.
    # lightning-30b is enabled, answers in a few seconds, and is the same
    # model family the memory/RAG agents already use. Swap in the ultra model
    # via LLM_MODEL_ANALYST when a run has time to spare.
    # Groq is not a fallback here: its free tier allows 8,000 tokens per
    # minute, and the analyst prompt alone pushes a run past that (413).
    "analyst": {
        "provider": os.getenv("LLM_PROVIDER_ANALYST", "nvidia"),
        "model": os.getenv("LLM_MODEL_ANALYST", "nvidia/nemotron-3.5-lightning-30b-a3b"),
    },
    # Guardrail review is small but important; Groq is fast and isolated from
    # the analyst provider so one provider's limits do not pause every agent.
    "guardrail": {
        "provider": os.getenv("LLM_PROVIDER_GUARDRAIL", "groq"),
        "model": os.getenv("LLM_MODEL_GUARDRAIL", "openai/gpt-oss-120b"),
    },
    "stress_test": {
        "provider": os.getenv("LLM_PROVIDER_STRESS_TEST", "groq"),
        "model": os.getenv("LLM_MODEL_STRESS_TEST", "openai/gpt-oss-20b"),
    },
    "report_writer": {
        "provider": os.getenv("LLM_PROVIDER_REPORT_WRITER", "openrouter"),
        "model": os.getenv("LLM_MODEL_REPORT_WRITER", "nvidia/nemotron-3.5-lightning:free"),
    },
    # Dashboard chatbot: short conversational answers grounded in one run.
    "chat": {
        "provider": os.getenv("LLM_PROVIDER_CHAT", "groq"),
        "model": os.getenv("LLM_MODEL_CHAT", "openai/gpt-oss-20b"),
    },
}

# Backward-compatible task -> model map for code/UI that only needs labels.
MODELS = {task: route["model"] for task, route in LLM_ROUTES.items()}

_llm_mock_env = os.getenv("LLM_MOCK_MODE", "auto").strip().lower()
if _llm_mock_env == "on":
    LLM_MOCK_MODE = True
elif _llm_mock_env == "off":
    LLM_MOCK_MODE = False
else:  # "auto"
    LLM_MOCK_MODE = not any([ANTHROPIC_API_KEY, NVIDIA_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY])

LLM_MAX_RETRIES = 2
# 30s was too tight for NVIDIA's Nemotron models on a real (non-trivial)
# prompt even with chain-of-thought disabled (services/llm.py) -- measured
# 19-20s for the analyst's ~2.2K-input-token prompt. 60s leaves headroom
# for slower free-tier responses without materially hurting the happy path.
LLM_TIMEOUT_SECONDS = 60
LLM_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# Materiality and priority scoring (plan section 5.2)
# ---------------------------------------------------------------------------

DEFAULT_MATERIALITY_THRESHOLD_USD = 5_000.0
DEFAULT_MATERIALITY_THRESHOLD_PCT = 0.05

# Must sum to 1.00 -- see plan section 5.2.
PRIORITY_SCORE_WEIGHTS = {
    "normalized_absolute_change": 0.35,
    "normalized_percentage_change": 0.20,
    "business_materiality": 0.20,
    "statistical_surprise": 0.15,
    "novelty_score": 0.10,
}
assert abs(sum(PRIORITY_SCORE_WEIGHTS.values()) - 1.0) < 1e-9

CONTROL_LIMIT_Z = 2.0
MIN_PERIODS_FOR_CONTROL_LIMITS = 3

# Data QA gate policy (plan section 6.2).
RECONCILIATION_BLOCK_THRESHOLD_PCT = 0.02


# ---------------------------------------------------------------------------
# Memory lifecycle (plan section 8.3)
# ---------------------------------------------------------------------------

MEMORY_CONFIRM_AFTER_CORROBORATIONS = 2
MEMORY_DISPUTE_AFTER_CONTRADICTIONS = 1
MEMORY_RETIRE_AFTER_CONTRADICTIONS = 2

MEMORY_CORROBORATION_BOOST = 0.08
MEMORY_CONTRADICTION_PENALTY = 0.25
MEMORY_DECAY_PER_UNOBSERVED_PERIOD = 0.98  # multiplicative
MEMORY_CONFIDENCE_CEILING = 0.98
MEMORY_CONFIDENCE_FLOOR = 0.05
MEMORY_RETRIEVAL_FLOOR = 0.35


# ---------------------------------------------------------------------------
# Guardrail / grounding verifier (plan section 10.1, 10.2)
# ---------------------------------------------------------------------------

GROUNDING_NUMERIC_TOLERANCE_PCT = 0.005  # 0.5%
MAX_REVISION_PASSES = 2

# confidence <= data_quality_score + this cap (plan section 10.2)
CONFIDENCE_DATA_QUALITY_SLACK = 0.10


# ---------------------------------------------------------------------------
# RAG (plan section 9)
# ---------------------------------------------------------------------------

RAG_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RAG_RETRIEVE_K = 4
RAG_RERANK_K = 2
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./.chroma")


# ---------------------------------------------------------------------------
# Sponsor integrations (plan section 16)
# ---------------------------------------------------------------------------

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_TIMEOUT_SECONDS = 5

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
VOICE_BRIEFING_MAX_SECONDS = 60


# ---------------------------------------------------------------------------
# Voice providers (services/voice_client.py)
# ---------------------------------------------------------------------------
# Default to the local open-source stack so voice works offline, with no API
# key and no per-call cost: Kokoro-82M (Apache-2.0 weights, run through ONNX
# Runtime) for speech, and faster-whisper (MIT, CTranslate2 port of Whisper)
# for transcription. Set either to "elevenlabs" to use the hosted provider.

VOICE_TTS_PROVIDER = os.getenv("VOICE_TTS_PROVIDER", "kokoro").strip().lower()
VOICE_STT_PROVIDER = os.getenv("VOICE_STT_PROVIDER", "whisper").strip().lower()

# Kokoro ships one checkpoint with many baked-in voices. "af_heart" is the
# highest-graded American English voice and the closest match to the calm,
# neutral narration the briefing used to get from ElevenLabs' "Rachel".
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_LANG = os.getenv("KOKORO_LANG", "en-us")
KOKORO_SPEED = _env_float("KOKORO_SPEED", 1.0)

# Weights are ~350MB, so they are downloaded once on first use rather than
# vendored: scripts/fetch_voice_models.py pre-fetches them before a demo.
KOKORO_MODEL_DIR = os.getenv("KOKORO_MODEL_DIR", "./.cache/kokoro")
KOKORO_MODEL_FILE = os.getenv("KOKORO_MODEL_FILE", "kokoro-v1.0.onnx")
KOKORO_VOICES_FILE = os.getenv("KOKORO_VOICES_FILE", "voices-v1.0.bin")
KOKORO_RELEASE_URL = os.getenv(
    "KOKORO_RELEASE_URL",
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1",
)

# "small.en" is the accuracy/latency sweet spot for the short spoken
# questions the chat panel sends; int8 on CPU keeps it off the GPU entirely.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small.en")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "en")
WHISPER_BEAM_SIZE = int(os.getenv("WHISPER_BEAM_SIZE", "5"))

# An ".en" model can only do English, so a Spanish question needs the
# multilingual checkpoint. Loaded only if a non-English language is asked for.
WHISPER_MODEL_MULTILINGUAL = os.getenv("WHISPER_MODEL_MULTILINGUAL", "small")

# Kokoro's Spanish voices are ef_dora, em_alex and em_santa.
KOKORO_VOICE_ES = os.getenv("KOKORO_VOICE_ES", "ef_dora")


# ---------------------------------------------------------------------------
# Translation (services/translator.py)
# ---------------------------------------------------------------------------
# Screen/UI translation runs on Helsinki-NLP's OPUS-MT models through
# transformers -- local, open-source and free, so there is no per-character
# bill like the Google Translate API's.

UI_DEFAULT_LANGUAGE = os.getenv("UI_DEFAULT_LANGUAGE", "en")
TRANSLATION_SUPPORTED_LANGUAGES = ("en", "es")
TRANSLATION_MODELS = {
    "en-es": os.getenv("TRANSLATION_MODEL_EN_ES", "Helsinki-NLP/opus-mt-en-es"),
    "es-en": os.getenv("TRANSLATION_MODEL_ES_EN", "Helsinki-NLP/opus-mt-es-en"),
}
# A screenful of labels fits comfortably; the caps stop one request from
# pinning the CPU for a minute.
TRANSLATION_MAX_TEXTS = int(os.getenv("TRANSLATION_MAX_TEXTS", "250"))
TRANSLATION_MAX_CHARS = int(os.getenv("TRANSLATION_MAX_CHARS", "2000"))


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ledgerlight.db")


# ---------------------------------------------------------------------------
# Latency budget (plan section 17.1) -- used for timeout guards, not enforced
# strictly, but surfaced in the agent timeline when a node overruns.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LatencyBudget:
    upload_parse_s: float = 1.5
    data_qa_s: float = 0.5
    analytics_s: float = 1.0
    memory_rag_s: float = 1.5
    analyst_s: float = 12.0
    grounding_s: float = 0.1
    guardrail_s: float = 5.0
    stress_tests_s: float = 2.0
    report_writer_s: float = 3.0
    total_hard_cap_s: float = 45.0


LATENCY_BUDGET = LatencyBudget()
