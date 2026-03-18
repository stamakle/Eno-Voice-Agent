import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:audioplayers/audioplayers.dart';
import 'package:http/http.dart' as http;
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../config/app_config.dart';

// Web Audio API playback via package:web + dart:js_interop.
// Only imported/used when kIsWeb is true (tree-shaken on native).
import 'web_audio_player.dart'
    if (dart.library.io) 'web_audio_player_stub.dart';
import 'native_audio_file_stub.dart'
    if (dart.library.io) 'native_audio_file_io.dart' as native_audio_file;

class SpeechClient {
  SpeechClient()
      : _recorder = AudioRecorder(),
        _player = kIsWeb ? null : AudioPlayer();

  final AudioRecorder _recorder;
  final AudioPlayer? _player;

  // Native playback completer.
  Completer<void>? _nativePlayCompleter;

  Future<bool> hasMicrophonePermission() {
    if (kIsWeb) {
      return _recorder.hasPermission(request: false);
    }
    return Permission.microphone.isGranted;
  }

  Future<void> ensureMicrophonePermission() async {
    if (kIsWeb) {
      final granted = await _recorder.hasPermission();
      if (!granted) {
        throw StateError('Microphone permission was denied.');
      }
      return;
    }

    var status = await Permission.microphone.status;
    if (status.isGranted) {
      return;
    }

    status = await Permission.microphone.request();
    if (status.isGranted) {
      return;
    }
    if (status.isPermanentlyDenied) {
      throw StateError(
        'Microphone permission is permanently denied. Open app settings and enable the microphone for Aura Coach.',
      );
    }
    if (status.isRestricted) {
      throw StateError(
        'Microphone permission is restricted on this device and cannot be enabled here.',
      );
    }

    throw StateError('Microphone permission was denied.');
  }

  Future<Stream<Uint8List>> startStreaming() async {
    await _configureNativeAudio();
    await ensureMicrophonePermission();

    await stopPlayback();
    final stream = await _recorder.startStream(
      const RecordConfig(
        encoder: AudioEncoder.pcm16bits,
        sampleRate: 16000,
        numChannels: 1,
      ),
    );
    return stream;
  }

  Stream<Amplitude> getAmplitudeStream() {
    return _recorder.onAmplitudeChanged(const Duration(milliseconds: 100));
  }

  Future<void> stopStreaming() async {
    await _recorder.stop();
  }

  Future<String> transcribe(Uint8List audioBytes, {String? authToken}) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('${AppConfig.apiBaseUrl}/api/audio/stt'),
    );
    if (authToken != null && authToken.isNotEmpty) {
      request.headers['Authorization'] = 'Bearer $authToken';
    }
    request.files.add(
      http.MultipartFile.fromBytes(
        'audio',
        audioBytes,
        filename: 'lesson.wav',
      ),
    );

    final streamedResponse = await request.send();
    final response = await http.Response.fromStream(streamedResponse);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError('STT failed: ${response.body}');
    }

    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    return payload['text'] as String? ?? '';
  }

  Future<void> speak(String text, {String? authToken}) async {
    final cleanText = text.trim();
    if (cleanText.isEmpty) return;

    final response = await http.post(
      Uri.parse('${AppConfig.apiBaseUrl}/api/audio/tts'),
      headers: <String, String>{
        'Content-Type': 'application/json',
        if (authToken != null && authToken.isNotEmpty)
          'Authorization': 'Bearer $authToken',
      },
      body: jsonEncode(<String, dynamic>{'text': cleanText}),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw StateError('TTS failed: ${response.body}');
    }

    await playAudioBytes(response.bodyBytes);
  }

  Future<void> playAudioBytes(Uint8List audioBytes) async {
    if (audioBytes.isEmpty) return;

    if (kIsWeb) {
      // Use the Web Audio API helper (web_audio_player.dart).
      await playAudioBytesInBrowser(audioBytes);
    } else {
      await _configureNativeAudio();
      await _playBytesNative(audioBytes);
    }
  }

  Future<void> primeAudioOutput() async {
    if (kIsWeb) {
      await prepareWebAudioPlayback();
      return;
    }
    await _configureNativeAudio();
  }

  Future<void> _configureNativeAudio() async {
    if (kIsWeb) {
      return;
    }
    final player = _player;
    if (player == null) {
      return;
    }

    final context = AudioContextConfig(
      route: AudioContextConfigRoute.speaker,
      focus: AudioContextConfigFocus.gain,
      respectSilence: false,
    ).build();

    await AudioPlayer.global.setAudioContext(context);
    await player.setAudioContext(context);
    await player.setPlayerMode(PlayerMode.mediaPlayer);
    await player.setReleaseMode(ReleaseMode.stop);
    await player.setVolume(1.0);

    final iosRecorder = _recorder.ios;
    if (iosRecorder != null) {
      await iosRecorder.setAudioSessionCategory(
        category: IosAudioCategory.playAndRecord,
        options: const [
          IosAudioCategoryOptions.defaultToSpeaker,
          IosAudioCategoryOptions.allowBluetooth,
          IosAudioCategoryOptions.allowBluetoothA2DP,
          IosAudioCategoryOptions.duckOthers,
        ],
      );
    }
  }

  /// Native: use audioplayers BytesSource.
  Future<void> _playBytesNative(Uint8List audioBytes) async {
    final player = _player!;
    final tempPath = await native_audio_file.persistAudioBytesToTempFile(
      audioBytes,
      extension: 'wav',
    );
    await player.stop();
    final completer = Completer<void>();
    _nativePlayCompleter = completer;
    late final StreamSubscription<void> sub;
    sub = player.onPlayerComplete.listen((_) {
      if (!completer.isCompleted) completer.complete();
      sub.cancel();
    });

    await player.play(DeviceFileSource(tempPath, mimeType: 'audio/wav'));

    try {
      await completer.future.timeout(const Duration(seconds: 30));
    } on TimeoutException {
      await sub.cancel();
    } finally {
      _nativePlayCompleter = null;
      await native_audio_file.deletePersistedAudioFile(tempPath);
    }
  }

  Future<void> stopPlayback() async {
    if (kIsWeb) {
      await stopWebAudioPlayback();
    } else {
      _nativePlayCompleter?.complete();
      _nativePlayCompleter = null;
      await _player?.stop();
    }
  }

  Future<void> dispose() async {
    await stopPlayback();
    await _player?.release();
    await _player?.dispose();
    await _recorder.dispose();
  }
}
