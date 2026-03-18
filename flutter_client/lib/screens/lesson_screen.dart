import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../models/api_models.dart';
import '../services/browser_voice_capability.dart'
    if (dart.library.io) '../services/browser_voice_capability_stub.dart';
import '../services/lesson_socket.dart';
import '../services/speech_client.dart';
import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import '../widgets/aura_widgets.dart';
import 'package:record/record.dart';

enum _LessonVoiceState { idle, speaking, listening, analyzing }

class LessonScreen extends StatefulWidget {
  const LessonScreen({
    super.key,
    required this.courseId,
    required this.chapterId,
    required this.lessonId,
  });

  final String courseId;
  final String chapterId;
  final String lessonId;

  @override
  State<LessonScreen> createState() => _LessonScreenState();
}

class _LessonScreenState extends State<LessonScreen> {
  late final LessonSocket _socket;
  final SpeechClient _speech = SpeechClient();
  final BrowserVoiceCapability _browserVoice = getBrowserVoiceCapability();

  StreamSubscription<Map<String, dynamic>>? _sub;
  StreamSubscription<Uint8List>? _micSub;
  StreamSubscription<Amplitude>? _ampSub;
  SessionSnapshot? _session;
  String? _correction;
  String? _summary;
  final List<_ChatEntry> _chat = [];
  final List<Uint8List> _assistantAudioQueue = [];

  _LessonVoiceState _voiceState = _LessonVoiceState.idle;
  bool _recording = false;
  bool _processing = false;
  bool _playingAssistantAudio = false;
  bool _audioUnlocked = false;
  BytesBuilder? _incomingAssistantAudio;
  String? _partialTranscript;
  String? _voiceNotice;
  Timer? _silenceTimer;

  @override
  void initState() {
    super.initState();
    _audioUnlocked = !_browserVoice.needsUserGestureForAudio;
    final token = context.read<AppState>().authToken!;
    _socket = LessonSocket(token: token);
    _sub = _socket.stream.listen(_onEvent);
    _socket.joinLesson(
      courseId: widget.courseId,
      chapterId: widget.chapterId,
      lessonId: widget.lessonId,
    );
  }

  Future<void> _onEvent(Map<String, dynamic> event) async {
    final type = event['type'] as String? ?? '';

    if (!mounted) return;

    switch (type) {
      case 'session_state':
        setState(() {
          _session = SessionSnapshot.fromJson(
              event['session'] as Map<String, dynamic>);
        });
        return;
      case 'assistant_message':
        final text = event['text'] as String? ?? '';
        if (text.isNotEmpty) {
          setState(() {
            _chat.add(_ChatEntry(text: text, isAura: true));
          });
        }
        return;
      case 'lesson_prompt':
        final ex =
            ExerciseModel.fromJson(event['exercise'] as Map<String, dynamic>);
        final retryPrompt = event['retry_prompt'] as String?;
        setState(() {
          _chat.add(_ChatEntry(text: '📝 ${ex.prompt}', isAura: true));
          if (retryPrompt != null && retryPrompt.isNotEmpty) {
            _correction = retryPrompt;
          }
        });
        return;
      case 'correction':
        setState(() {
          _correction = event['text'] as String?;
          _chat.add(_ChatEntry(text: '💡 ${_correction ?? ''}', isAura: true));
        });
        return;
      case 'assistant_summary':
        setState(() {
          _summary = event['text'] as String?;
          _chat.add(_ChatEntry(text: '🎉 ${_summary ?? ''}', isAura: true));
        });
        return;
      case 'lesson_completed':
        setState(() {
          _chat.add(_ChatEntry(
              text: '✅ ${event['text'] ?? 'Lesson saved!'}', isAura: true));
        });
        return;
      case 'stt_result':
        final transcript = event['text'] as String? ?? '';
        setState(() {
          _processing = false;
          _partialTranscript = null;
          _voiceState = _LessonVoiceState.analyzing;
          if (transcript.trim().isNotEmpty) {
            _chat.add(_ChatEntry(text: transcript, isAura: false));
          } else {
            _chat.add(_ChatEntry(text: '(no speech detected)', isAura: false));
            _voiceState = _LessonVoiceState.idle;
          }
        });
        return;
      case 'stt_partial':
        setState(() {
          _partialTranscript = event['text'] as String?;
        });
        return;
      case 'assistant_audio_start':
        _incomingAssistantAudio = BytesBuilder(copy: false);
        setState(() => _voiceState = _LessonVoiceState.speaking);
        return;
      case 'assistant_audio_chunk':
        final data = event['data'] as String?;
        if (data != null && data.isNotEmpty) {
          _incomingAssistantAudio ??= BytesBuilder(copy: false);
          _incomingAssistantAudio!.add(base64Decode(data));
        }
        return;
      case 'assistant_audio_complete':
        final incoming = _incomingAssistantAudio;
        _incomingAssistantAudio = null;
        if (incoming != null) {
          _assistantAudioQueue.add(Uint8List.fromList(incoming.takeBytes()));
          unawaited(_drainAssistantAudioQueue());
        }
        return;
      case 'assistant_audio_error':
        final message = (event['message'] as String? ?? '').trim();
        setState(() {
          _voiceState = _LessonVoiceState.idle;
          if (message.isNotEmpty) {
            _voiceNotice = 'Aura could not play audio on this device. $message';
          }
        });
        return;
      case 'error':
        final message = (event['message'] as String? ?? '').trim().isEmpty
            ? 'I encountered an issue. Please try again in a moment.'
            : (event['message'] as String).trim();
        setState(() {
          _processing = false;
          _voiceState = _LessonVoiceState.idle;
          _chat.add(_ChatEntry(text: '⚠️ $message', isAura: true));
        });
        return;
    }
  }

  Future<void> _drainAssistantAudioQueue() async {
    if (_playingAssistantAudio) {
      return;
    }
    _playingAssistantAudio = true;
    String? playbackIssue;
    try {
      while (_assistantAudioQueue.isNotEmpty) {
        final bytes = _assistantAudioQueue.first;
        try {
          await _speech.playAudioBytes(bytes);
          _assistantAudioQueue.removeAt(0);
        } catch (error) {
          playbackIssue ??= _audioPlaybackMessage(error);
          break;
        }
      }
    } finally {
      _playingAssistantAudio = false;
      if (mounted && !_recording && !_processing) {
        setState(() => _voiceState = _LessonVoiceState.idle);
      }
    }
    if (mounted && playbackIssue != null) {
      setState(() {
        _voiceNotice = playbackIssue;
      });
    }
  }

  String? _voiceBannerMessage() {
    if (_assistantAudioQueue.isNotEmpty &&
        !_audioUnlocked &&
        _browserVoice.isWebPlatform) {
      return 'Tap anywhere to enable audio and hear Aura\'s reply on this phone.';
    }
    if (_voiceNotice != null && _voiceNotice!.trim().isNotEmpty) {
      return _voiceNotice;
    }
    if (_browserVoice.blockingReason != null &&
        _browserVoice.blockingReason!.trim().isNotEmpty) {
      return _browserVoice.blockingReason;
    }
    if (_browserVoice.isWebPlatform && !_audioUnlocked) {
      return 'Tap the mic once to enable sound in this browser.';
    }
    return null;
  }

  String _audioPlaybackMessage(Object error) {
    final detail = error.toString().toLowerCase();
    if (_browserVoice.isWebPlatform &&
        (detail.contains('user gesture') ||
            detail.contains('notallowed') ||
            detail.contains('resume') ||
            detail.contains('gesture') ||
            detail.contains('suspend'))) {
      return 'Tap anywhere to enable audio on this phone, then Aura will play the pending reply.';
    }
    return 'Audio playback is unavailable right now. The lesson text is still visible.';
  }

  String _microphoneErrorMessage(Object error) {
    if (_browserVoice.blockingReason != null) {
      return _browserVoice.blockingReason!;
    }
    final detail = error.toString().toLowerCase();
    if (detail.contains('permanently denied') ||
        detail.contains('app settings')) {
      return 'Microphone access is blocked for this app. Open your phone settings, allow Microphone for Aura Coach, then tap the mic again.';
    }
    if (detail.contains('restricted')) {
      return 'Microphone access is restricted on this device.';
    }
    if (detail.contains('permission')) {
      return 'Microphone permission was denied. Allow mic access, then tap the mic again.';
    }
    return 'I could not start the microphone on this device.';
  }

  Future<bool> _prepareVoiceInteraction({required bool microphone}) async {
    if (microphone && !_browserVoice.canCaptureMicrophone) {
      if (mounted) {
        setState(() {
          _voiceNotice = _browserVoice.blockingReason ??
              'Microphone capture is unavailable on this device.';
        });
      }
      return false;
    }

    try {
      if (microphone) {
        await _speech.ensureMicrophonePermission();
      }
      await _speech.primeAudioOutput();
      if (!mounted) {
        return true;
      }
      setState(() {
        _audioUnlocked = true;
        if (_voiceNotice ==
                'Tap the mic once to enable sound in this browser.' ||
            (_voiceNotice?.contains('enable audio on this phone') ?? false)) {
          _voiceNotice = null;
        }
      });
      return true;
    } catch (error) {
      final message = microphone
          ? _microphoneErrorMessage(error)
          : _audioPlaybackMessage(error);
      if (mounted) {
        setState(() {
          _voiceNotice = message;
        });
      }
      return !microphone;
    }
  }

  Future<void> _handleUserAudioUnlock() async {
    if (_audioUnlocked && _assistantAudioQueue.isEmpty) {
      return;
    }
    final ready = await _prepareVoiceInteraction(microphone: false);
    if (!ready || !mounted) {
      return;
    }
    if (_assistantAudioQueue.isNotEmpty && !_playingAssistantAudio) {
      await _drainAssistantAudioQueue();
    }
  }

  Future<void> _toggleMic() async {
    if (_processing) return;

    if (_recording) {
      setState(() {
        _recording = false;
        _voiceState = _LessonVoiceState.analyzing;
        _processing = true;
      });
      _silenceTimer?.cancel();
      _silenceTimer = null;
      await _ampSub?.cancel();
      _ampSub = null;
      await _micSub?.cancel();
      _micSub = null;
      try {
        await _speech.stopStreaming();
      } catch (_) {
        // Ignore stop failures; commit the buffered audio on the server anyway.
      }
      _socket.commitAudioInput();
      return;
    }

    try {
      final ready = await _prepareVoiceInteraction(microphone: true);
      if (!ready) {
        return;
      }
      _assistantAudioQueue.clear();
      _incomingAssistantAudio = null;
      await _speech.stopPlayback();
      final stream = await _speech.startStreaming();
      _socket.startAudioInput(sampleRate: 16000);
      _micSub = stream.listen(
        (chunk) {
          _socket.sendAudioChunk(chunk);
        },
        onError: (_) {
          if (!mounted) return;
          setState(() {
            _recording = false;
            _processing = false;
            _voiceState = _LessonVoiceState.idle;
            _chat.add(const _ChatEntry(
                text:
                    '🎙️ I lost connection to the server. Please check your internet and tap the microphone to try again.',
                isAura: true));
          });
        },
      );

      _silenceTimer?.cancel();
      _silenceTimer = null;
      _ampSub = _speech.getAmplitudeStream().listen((amp) {
        if (!mounted || !_recording) return;
        if (amp.current < -38.0) {
          _silenceTimer ??= Timer(const Duration(milliseconds: 1500), () {
            if (_recording && mounted) {
              _toggleMic();
            }
          });
        } else {
          _silenceTimer?.cancel();
          _silenceTimer = null;
        }
      });

      setState(() {
        _voiceNotice = null;
        _recording = true;
        _partialTranscript = null;
        _voiceState = _LessonVoiceState.listening;
      });
    } catch (e) {
      final message = _microphoneErrorMessage(e);
      setState(() {
        _voiceNotice = message;
        _chat.add(_ChatEntry(text: '🎙️ $message', isAura: true));
      });
    }
  }

  Future<void> _completeLesson() async {
    _socket.completeLesson(
      notes: const ['Completed via Aura Flutter client'],
      weakTopics: const [],
    );
  }

  @override
  void dispose() {
    _silenceTimer?.cancel();
    _ampSub?.cancel();
    _micSub?.cancel();
    _sub?.cancel();
    _socket.dispose();
    _speech.dispose();
    super.dispose();
  }

  String get _avatarState {
    switch (_voiceState) {
      case _LessonVoiceState.speaking:
        return 'speaking';
      case _LessonVoiceState.listening:
        return 'listening';
      case _LessonVoiceState.analyzing:
        return 'analyzing';
      case _LessonVoiceState.idle:
        return 'idle';
    }
  }

  @override
  Widget build(BuildContext context) {
    final ready = _session?.status == 'ready_for_completion';
    final statusLabel = _session?.status ?? 'Connecting…';
    final voiceBannerMessage = _voiceBannerMessage();

    return Scaffold(
      body: Container(
        decoration:
            const BoxDecoration(gradient: AuraColors.backgroundGradient),
        child: SafeArea(
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerDown: (_) {
              unawaited(_handleUserAudioUnlock());
            },
            child: Column(
              children: [
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: Row(
                    children: [
                      GestureDetector(
                        onTap: () => Navigator.of(context).pop(),
                        child: Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: AuraColors.cardDark,
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(color: AuraColors.borderDark),
                          ),
                          child: const Icon(Icons.arrow_back_ios_new,
                              size: 18, color: AuraColors.textPrimary),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _session?.lessonTitle ?? widget.lessonId,
                              style: GoogleFonts.spaceGrotesk(
                                fontWeight: FontWeight.w700,
                                fontSize: 16,
                                color: AuraColors.textPrimary,
                              ),
                              overflow: TextOverflow.ellipsis,
                            ),
                            Text(
                              statusLabel,
                              style: const TextStyle(
                                  color: AuraColors.textSecondary,
                                  fontSize: 12),
                            ),
                          ],
                        ),
                      ),
                      if (ready)
                        ElevatedButton(
                          onPressed: _completeLesson,
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 14, vertical: 8),
                          ),
                          child: const Text('Complete'),
                        ),
                    ],
                  ),
                ),
                AuraAvatar(state: _avatarState, size: 120),
                const SizedBox(height: 8),
                if (voiceBannerMessage != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 12,
                      ),
                      decoration: BoxDecoration(
                        color: (_browserVoice.blockingReason != null
                                ? AuraColors.warning
                                : AuraColors.primary)
                            .withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(
                          color: (_browserVoice.blockingReason != null
                                  ? AuraColors.warning
                                  : AuraColors.primary)
                              .withValues(alpha: 0.28),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            _browserVoice.blockingReason != null
                                ? Icons.info_outline_rounded
                                : Icons.volume_up_rounded,
                            color: _browserVoice.blockingReason != null
                                ? AuraColors.warning
                                : AuraColors.primary,
                            size: 18,
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: Text(
                              voiceBannerMessage,
                              style: GoogleFonts.spaceGrotesk(
                                color: AuraColors.textPrimary,
                                fontSize: 12.5,
                                fontWeight: FontWeight.w500,
                                height: 1.4,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                if (voiceBannerMessage != null) const SizedBox(height: 10),
                if (_session != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Column(
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              'Exercise ${_session!.currentAttempt}/${_session!.currentMaxAttempts}',
                              style: const TextStyle(
                                  color: AuraColors.textSecondary,
                                  fontSize: 12),
                            ),
                            Text(
                              '${_session!.completedExercises.length} done',
                              style: const TextStyle(
                                color: AuraColors.primary,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        ClipRRect(
                          borderRadius: BorderRadius.circular(999),
                          child: LinearProgressIndicator(
                            value: _session!.currentMaxAttempts == 0
                                ? 0
                                : _session!.currentAttempt /
                                    _session!.currentMaxAttempts,
                            backgroundColor: AuraColors.borderDark,
                            valueColor: const AlwaysStoppedAnimation(
                                AuraColors.primary),
                            minHeight: 6,
                          ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: 12),
                if (_partialTranscript != null &&
                    _partialTranscript!.trim().isNotEmpty)
                  Padding(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
                    child: GlassCard(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          const Icon(Icons.hearing_rounded,
                              color: AuraColors.primary, size: 18),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _partialTranscript!,
                              style: const TextStyle(
                                color: AuraColors.textSecondary,
                                fontSize: 13,
                                height: 1.35,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                    itemCount: _chat.length,
                    itemBuilder: (_, i) {
                      final e = _chat[i];
                      return Align(
                        alignment: e.isAura
                            ? Alignment.centerLeft
                            : Alignment.centerRight,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          padding: const EdgeInsets.symmetric(
                              horizontal: 14, vertical: 10),
                          constraints: BoxConstraints(
                              maxWidth:
                                  MediaQuery.of(context).size.width * 0.78),
                          decoration: BoxDecoration(
                            color: e.isAura
                                ? AuraColors.cardDark
                                : AuraColors.primary.withValues(alpha: 0.16),
                            borderRadius: BorderRadius.only(
                              topLeft: const Radius.circular(16),
                              topRight: const Radius.circular(16),
                              bottomLeft: Radius.circular(e.isAura ? 4 : 16),
                              bottomRight: Radius.circular(e.isAura ? 16 : 4),
                            ),
                            border: Border.all(
                              color: e.isAura
                                  ? AuraColors.borderDark
                                  : AuraColors.primary.withValues(alpha: 0.3),
                            ),
                          ),
                          child: Text(
                            e.text,
                            style: const TextStyle(
                              color: AuraColors.textPrimary,
                              fontSize: 14,
                              height: 1.4,
                            ),
                          ),
                        )
                            .animate()
                            .fadeIn(duration: 250.ms)
                            .slideY(begin: 0.15),
                      );
                    },
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(bottom: 24, top: 8),
                  child: Column(
                    children: [
                      if (_voiceState == _LessonVoiceState.analyzing)
                        const AuraStatusBadge(
                            text: 'Analyzing…', color: AuraColors.warning)
                      else if (_voiceState == _LessonVoiceState.listening)
                        const AuraStatusBadge(
                            text: 'Listening…', color: Color(0xFF22C55E))
                      else if (_voiceState == _LessonVoiceState.speaking)
                        const AuraStatusBadge(
                            text: 'Speaking…', color: AuraColors.primary),
                      const SizedBox(height: 12),
                      MicButton(
                        isRecording: _recording,
                        isProcessing: _processing,
                        onTap: _toggleMic,
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ChatEntry {
  const _ChatEntry({required this.text, required this.isAura});
  final String text;
  final bool isAura;
}
