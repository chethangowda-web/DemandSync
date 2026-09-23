import 'package:flutter_tts/flutter_tts.dart';

/// Thin text-to-speech wrapper. Speaks assistant answers aloud so low-literacy
/// beneficiaries can hear responses, not just read them. No speech recognition —
/// input stays typed/tapped.
class VoiceSpeaker {
  VoiceSpeaker() : _tts = FlutterTts();
  final FlutterTts _tts;

  static const _ttsLocale = {'en': 'en-IN', 'hi': 'hi-IN', 'kn': 'kn-IN'};

  Future<void> speak(String text, String languageCode) async {
    if (text.trim().isEmpty) return;
    await _tts.stop();
    await _tts.setLanguage(_ttsLocale[languageCode] ?? 'en-IN');
    await _tts.setSpeechRate(0.45);
    await _tts.speak(text);
  }

  Future<void> stop() => _tts.stop();
}
