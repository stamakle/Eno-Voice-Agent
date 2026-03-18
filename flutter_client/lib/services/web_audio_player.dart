// Web Audio API player using package:web and dart:js_interop.
// This file is only compiled when targeting browser (dart.library.html).
import 'dart:async';
import 'dart:js_interop';
import 'dart:typed_data';

import 'package:web/web.dart' as web;

Completer<void>? _activeCompleter;
web.AudioContext? _audioContext;
web.AudioBufferSourceNode? _activeSource;

Future<void> prepareWebAudioPlayback() async {
  final context = _audioContext ??= web.AudioContext();
  if (context.state == 'suspended') {
    await context.resume().toDart;
  }
  if (context.state != 'running') {
    throw StateError('Audio playback requires a user gesture.');
  }
}

/// Plays raw WAV bytes using the browser's Web Audio API (AudioContext).
/// AudioContext.decodeAudioData handles any PCM WAV format including
/// non-standard sample rates like 22050Hz that Chrome's HTML5 Audio rejects.
Future<void> playAudioBytesInBrowser(Uint8List audioBytes) async {
  // Cancel any active playback.
  if (_activeCompleter != null && !_activeCompleter!.isCompleted) {
    _activeCompleter!.complete();
  }

  final completer = Completer<void>();
  _activeCompleter = completer;

  final audioBytesCopy = Uint8List.fromList(audioBytes);
  await prepareWebAudioPlayback();
  final context = _audioContext!;
  final jsBuffer = audioBytesCopy.buffer.toJS;
  final audioBuffer = await context.decodeAudioData(jsBuffer).toDart;
  final source = context.createBufferSource();
  _activeSource?.stop();
  _activeSource = source;
  source.buffer = audioBuffer;
  source.connect(context.destination);

  source.addEventListener(
    'ended',
    (web.Event _) {
      if (!completer.isCompleted) {
        completer.complete();
      }
    }.toJS,
  );

  source.start();

  try {
    await completer.future.timeout(
      const Duration(seconds: 60),
      onTimeout: () {
        if (!completer.isCompleted) {
          completer.complete();
        }
        source.stop();
      },
    );
  } finally {
    if (identical(_activeSource, source)) {
      _activeSource = null;
    }
    if (identical(_activeCompleter, completer)) {
      _activeCompleter = null;
    }
  }
}

Future<void> stopWebAudioPlayback() async {
  _activeSource?.stop();
  _activeSource = null;
  if (_activeCompleter != null && !_activeCompleter!.isCompleted) {
    _activeCompleter!.complete();
  }
  _activeCompleter = null;
}
