// Stub for non-web platforms (native iOS, Android, desktop).
// The web_audio_player.dart provides the real implementation for browsers.
import 'dart:async';
import 'dart:typed_data';

Future<void> playAudioBytesInBrowser(Uint8List audioBytes) async {
  // No-op on native — SpeechClient uses audioplayers directly on native.
}

Future<void> stopWebAudioPlayback() async {
  // No-op on native.
}

Future<void> prepareWebAudioPlayback() async {
  // No-op on native.
}
