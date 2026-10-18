# Qwen3-TTS voice integration (v0.1.83)

JINKAKU includes an optional Android ARM64 native Qwen3-TTS voice module.
- The chat LLM remains Gemma 4 E2B LiteRT-LM; Persona and Memory are untouched.
- Tap the speaker icon in Chat, download the 0.6B Q4_K_M model (two GGUF files, about 884 MB), optionally select a PCM WAV speaker sample, then read the most recent AI response.
- Speaker samples are stored locally and keyed by Persona text; the audio and voice data are never sent to the service by JINKAKU.
- Native C++ runtime is based on the MIT-licensed `Danmoreng/qwen3-tts.cpp` and Qwen3 Android reference (MIT). Source is included as a recursively checked-out git submodule.
- The runtime currently runs on CPU and generates then plays audio (not streaming). Playback in Japanese is configured with language ID 2058.
- The model files come from `Serveurperso/Qwen3-TTS-GGUF` on Hugging Face. Review third-party licenses before redistribution. The GGUF weights are downloaded by the user, not bundled into the APK.
- For safety and device stability, the first version limits playback to the latest AI response (240 chars). It does not clone a voice without an authorized reference and does not change Chat or Memory contents.
- Release-equivalent building requires recursive submodule checkout and the normal sequential patch pipeline in `.github/workflows/android.yml`.
- App runtime and voice quality require on-device verification.
