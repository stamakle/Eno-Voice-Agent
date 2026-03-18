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
import '../services/coach_socket.dart';
import '../services/speech_client.dart';
import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import '../widgets/aura_widgets.dart';
import 'lesson_screen.dart';
import 'package:record/record.dart';

class CoachScreen extends StatefulWidget {
  const CoachScreen({super.key});

  @override
  State<CoachScreen> createState() => _CoachScreenState();
}

class _CoachScreenState extends State<CoachScreen> with WidgetsBindingObserver {
  final SpeechClient _speech = SpeechClient();
  final BrowserVoiceCapability _browserVoice = getBrowserVoiceCapability();
  final List<_ChatMessage> _messages = [];
  final ScrollController _scroll = ScrollController();
  final List<Uint8List> _assistantAudioQueue = [];
  final TextEditingController _textController = TextEditingController();

  CoachSocket? _coachSocket;
  StreamSubscription<Map<String, dynamic>>? _socketSub;
  StreamSubscription<Uint8List>? _micSub;
  StreamSubscription<Amplitude>? _ampSub;
  Timer? _silenceTimer;
  Timer? _reconnectTimer;
  bool _recording = false;
  bool _processing = false;
  bool _playingAssistantAudio = false;
  bool _audioUnlocked = false;
  bool _voiceInputArmed = false;
  bool _resumeMicAfterPendingAudio = false;
  bool _showBootstrapDetails = false;
  String _socketStatus = 'Connecting…';
  String? _partialTranscript;
  String? _voiceNotice;
  BytesBuilder? _incomingAssistantAudio;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _audioUnlocked = !_browserVoice.needsUserGestureForAudio;
    _voiceInputArmed = !_browserVoice.needsUserGestureForAudio;
    WidgetsBinding.instance.addPostFrameCallback((_) => _connectCoachSocket());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _silenceTimer?.cancel();
    _reconnectTimer?.cancel();
    _ampSub?.cancel();
    _micSub?.cancel();
    _socketSub?.cancel();
    _coachSocket?.dispose();
    _speech.dispose();
    _scroll.dispose();
    _textController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed || !mounted) {
      return;
    }
    if (_socketStatus == 'Disconnected' || _socketStatus == 'Reconnecting…') {
      unawaited(_connectCoachSocket());
      return;
    }
    _coachSocket?.requestBootstrap();
  }

  void _scheduleReconnect() {
    if (!mounted) {
      return;
    }
    _reconnectTimer?.cancel();
    setState(() => _socketStatus = 'Reconnecting…');
    _reconnectTimer = Timer(const Duration(seconds: 2), () {
      if (mounted) {
        unawaited(_connectCoachSocket());
      }
    });
  }

  Future<void> _connectCoachSocket() async {
    final state = context.read<AppState>();
    final token = state.authToken;
    if (token == null || token.isEmpty) {
      return;
    }

    if (mounted) {
      setState(() {
        _socketStatus = 'Connecting…';
        if (_socketStatus != 'Connected') {
          _voiceNotice = null;
        }
      });
    }

    _reconnectTimer?.cancel();
    await _socketSub?.cancel();
    _coachSocket?.dispose();
    _coachSocket = CoachSocket(token: token);
    _socketSub = _coachSocket!.stream.listen(
      (event) => _onSocketEvent(event, state),
      onError: (e) {
        debugPrint('CoachSocket Error: $e');
        _scheduleReconnect();
      },
      onDone: () {
        debugPrint('CoachSocket Closed');
        _scheduleReconnect();
      },
    );
  }

  Future<void> _onSocketEvent(
      Map<String, dynamic> event, AppState state) async {
    final type = event['type'] as String? ?? '';
    switch (type) {
      case 'coach_session':
        if (!mounted) return;
        setState(() => _socketStatus = 'Connected');
        return;
      case 'coach_bootstrap':
        final bootstrap = CoachBootstrapModel.fromJson(
          event['bootstrap'] as Map<String, dynamic>? ?? <String, dynamic>{},
        );
        state.applyCoachBootstrap(bootstrap);
        return;
      case 'coach_reply':
        final text = event['text'] as String? ?? '';
        if (text.trim().isEmpty) return;
        _addMessage('Aura', text, isAura: true);
        state.setVoiceState(VoiceState.speaking, text: 'Speaking…');
        return;
      case 'coach_audio_start':
        _incomingAssistantAudio = BytesBuilder(copy: false);
        state.setVoiceState(VoiceState.speaking, text: 'Speaking…');
        return;
      case 'coach_audio_chunk':
        final data = event['data'] as String?;
        if (data != null && data.isNotEmpty) {
          _incomingAssistantAudio ??= BytesBuilder(copy: false);
          _incomingAssistantAudio!.add(base64Decode(data));
        }
        return;
      case 'coach_audio_complete':
        final incoming = _incomingAssistantAudio;
        _incomingAssistantAudio = null;
        final isFinal = event['is_final_segment'] as bool? ?? true;
        if (incoming != null) {
          _assistantAudioQueue.add(Uint8List.fromList(incoming.takeBytes()));
          _drainAssistantAudioQueue(state, autoStartMicWhenDone: isFinal);
        } else if (isFinal) {
          // No audio bytes arrived, but greeting is done — auto-start anyway.
          _autoStartMicIfNeeded(state);
        }
        return;
      case 'coach_audio_error':
        final message = (event['message'] as String? ?? '').trim();
        if (message.isNotEmpty) {
          _setVoiceNotice(
            'Aura could not play audio on this device. $message',
          );
        }
        state.setVoiceState(VoiceState.idle);
        return;
      case 'stt_partial':
        if (!mounted) return;
        setState(() => _partialTranscript = event['text'] as String?);
        return;
      case 'stt_result':
        final transcript = event['text'] as String? ?? '';
        final int fillerWords = event['filler_words'] as int? ?? 0;
        final int totalWords = event['total_words'] as int? ?? 0;
        final double lexicalDiversity =
            (event['lexical_diversity'] as num?)?.toDouble() ?? 0.0;
        if (!mounted) return;
        setState(() {
          _processing = false;
          _partialTranscript = null;
          if (transcript.trim().isEmpty) {
            _messages.add(const _ChatMessage(
                sender: 'You', text: '(no speech detected)', isAura: false));
          } else {
            _messages.add(_ChatMessage(
              sender: 'You',
              text: transcript,
              isAura: false,
              fillerWords: fillerWords,
              totalWords: totalWords,
              lexicalDiversity: lexicalDiversity,
            ));
          }
        });
        state.setVoiceState(VoiceState.analyzing, text: 'Analyzing…');
        return;
      case 'open_lesson':
        final lesson = NextLessonSelectionModel.fromJson(
          event['lesson'] as Map<String, dynamic>? ?? <String, dynamic>{},
        );
        if (!mounted) return;
        await Navigator.of(context).push(MaterialPageRoute<void>(
          builder: (_) => LessonScreen(
            courseId: lesson.courseId,
            chapterId: lesson.chapterId,
            lessonId: lesson.lessonId,
          ),
        ));
        if (!mounted) return;
        await state.refresh();
        _coachSocket?.requestBootstrap();
        return;
      case 'error':
        final message = (event['message'] as String? ?? '').trim().isEmpty
            ? 'I encountered an issue. Please try again in a moment.'
            : (event['message'] as String).trim();
        _addMessage('Aura', message, isAura: true);
        state.setVoiceState(VoiceState.idle);
        return;
    }
  }

  Future<void> _drainAssistantAudioQueue(AppState state,
      {bool autoStartMicWhenDone = false}) async {
    if (_playingAssistantAudio) {
      if (autoStartMicWhenDone) {
        _resumeMicAfterPendingAudio = true;
      }
      return;
    }
    if (autoStartMicWhenDone) {
      _resumeMicAfterPendingAudio = true;
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
      if (!_recording && !_processing) {
        state.setVoiceState(VoiceState.idle);
      }
    }
    if (playbackIssue != null) {
      _setVoiceNotice(playbackIssue);
    }
    if (_assistantAudioQueue.isEmpty && _resumeMicAfterPendingAudio) {
      _resumeMicAfterPendingAudio = false;
      _autoStartMicIfNeeded(state);
    }
  }

  void _autoStartMicIfNeeded(AppState state) {
    if (_recording ||
        _processing ||
        !mounted ||
        _socketStatus != 'Connected' ||
        !_voiceInputArmed ||
        !_browserVoice.canCaptureMicrophone) {
      return;
    }
    // Small delay gives browser a moment after audio finishes.
    Future.delayed(const Duration(milliseconds: 400), () {
      if (mounted && !_recording && !_processing) {
        // Only auto-resume after the user has explicitly armed voice input.
        _toggleMic(silentOnError: true);
      }
    });
  }

  void _setVoiceNotice(String? message) {
    if (!mounted) {
      return;
    }
    setState(() {
      _voiceNotice = message;
    });
  }

  String? _voiceBannerMessage() {
    if (_socketStatus == 'Connecting…') {
      return 'Connecting to Aura now. Voice and replies will start as soon as the coach is ready.';
    }
    if (_socketStatus == 'Reconnecting…') {
      return 'Connection dropped. Aura is reconnecting now.';
    }
    if (_socketStatus == 'Disconnected') {
      return 'Aura is offline right now. Check your connection, then retry.';
    }
    if (_assistantAudioQueue.isNotEmpty &&
        !_audioUnlocked &&
        _browserVoice.isWebPlatform) {
      return 'Tap anywhere to enable audio and play Aura\'s reply on this phone.';
    }
    if (_voiceNotice != null && _voiceNotice!.trim().isNotEmpty) {
      return _voiceNotice;
    }
    if (_browserVoice.blockingReason != null &&
        _browserVoice.blockingReason!.trim().isNotEmpty) {
      return _browserVoice.blockingReason;
    }
    if (_browserVoice.isWebPlatform && !_audioUnlocked) {
      return 'Tap Send or the mic once to enable sound in this browser.';
    }
    if (_browserVoice.isProbablyMobile && !_voiceInputArmed) {
      return 'Tap the mic to start voice input on this device.';
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
    return 'Audio playback is unavailable right now. Text chat still works.';
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
      return 'Microphone access is restricted on this device. Text chat still works.';
    }
    if (detail.contains('permission')) {
      return 'Microphone permission was denied. Allow mic access, then tap the mic again.';
    }
    return 'I could not start the microphone on this device. Text chat still works.';
  }

  Future<bool> _prepareVoiceInteraction({
    required bool microphone,
    bool silent = false,
  }) async {
    if (microphone && !_browserVoice.canCaptureMicrophone) {
      final message = _browserVoice.blockingReason ??
          'Microphone capture is unavailable on this device.';
      _setVoiceNotice(message);
      if (!silent) {
        _addMessage('Aura', message, isAura: true);
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
        if (_voiceNotice != null &&
            (_voiceNotice ==
                    'Tap Send or the mic once to enable sound in this browser.' ||
                _voiceNotice!.contains('enable audio on this phone'))) {
          _voiceNotice = null;
        }
      });
      return true;
    } catch (error) {
      final message = microphone
          ? _microphoneErrorMessage(error)
          : _audioPlaybackMessage(error);
      _setVoiceNotice(message);
      return !microphone;
    }
  }

  void _addMessage(String sender, String text, {required bool isAura}) {
    setState(() {
      _messages.add(_ChatMessage(sender: sender, text: text, isAura: isAura));
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  Future<void> _sendTypedReply() async {
    final text = _textController.text.trim();
    if (text.isEmpty) {
      return;
    }
    FocusScope.of(context).unfocus();
    await _prepareVoiceInteraction(microphone: false, silent: true);
    _assistantAudioQueue.clear();
    _incomingAssistantAudio = null;
    _playingAssistantAudio = false;
    await _speech.stopPlayback();
    _coachSocket?.sendLearnerText(text);
    _textController.clear();
  }

  Future<void> _handleUserAudioUnlock(AppState state) async {
    // If the user taps the overlay or anywhere, we prime the audio system
    // and also ARM the voice input so the conversation becomes hands-free.
    final alreadyUnlocked = _audioUnlocked;
    final ready = await _prepareVoiceInteraction(
      microphone: false,
      silent: true,
    );
    if (!ready || !mounted) {
      return;
    }

    if (_browserVoice.needsUserGestureForAudio) {
      setState(() => _voiceInputArmed = true);
    }

    if (_assistantAudioQueue.isNotEmpty && !_playingAssistantAudio) {
      await _drainAssistantAudioQueue(
        state,
        autoStartMicWhenDone: true,
      );
    } else if (!alreadyUnlocked && !_playingAssistantAudio) {
      _autoStartMicIfNeeded(state);
    }
  }

  Widget _buildLevelSelector() {
    TextButton buildLevelButton(String label, String level) {
      return TextButton(
        onPressed: () => context.read<AppState>().selectLevel(level),
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 0),
          minimumSize: Size.zero,
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
        child: Text(
          label,
          style: const TextStyle(
            fontSize: 10,
            color: AuraColors.textSecondary,
          ),
        ),
      );
    }

    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 4,
      runSpacing: 4,
      children: [
        Text(
          context.read<AppState>().levelBand.toUpperCase(),
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.5,
            color: {
                  'beginner': const Color(0xFF22C55E),
                  'intermediate': const Color(0xFFF59E0B),
                  'fluent': AuraColors.primary,
                }[context.read<AppState>().levelBand] ??
                AuraColors.primary,
          ),
        ),
        const SizedBox(width: 4),
        buildLevelButton('B', 'beginner'),
        buildLevelButton('I', 'intermediate'),
        buildLevelButton('A', 'fluent'),
      ],
    );
  }

  Future<void> _toggleMic({bool silentOnError = false}) async {
    if (_processing) return;
    final state = context.read<AppState>();

    if (_recording) {
      setState(() => _recording = false);
      _processing = true;
      state.setVoiceState(VoiceState.analyzing, text: 'Analyzing…');
      _silenceTimer?.cancel();
      _silenceTimer = null;
      await _ampSub?.cancel();
      _ampSub = null;
      await _micSub?.cancel();
      _micSub = null;
      try {
        await _speech.stopStreaming();
      } catch (_) {
        // Ignore stop failures; commit buffered audio anyway.
      }
      _coachSocket?.commitAudioInput();
      return;
    }

    if (_socketStatus != 'Connected' || _coachSocket == null) {
      const message =
          'Aura is not connected yet. Wait a moment for the coach to reconnect, then tap the mic again.';
      _setVoiceNotice(message);
      if (!silentOnError) {
        _addMessage('Aura', message, isAura: true);
      }
      return;
    }

    try {
      final ready = await _prepareVoiceInteraction(
        microphone: true,
        silent: silentOnError,
      );
      if (!ready) {
        return;
      }
      _assistantAudioQueue.clear();
      _incomingAssistantAudio = null;
      await _speech.stopPlayback();
      final stream = await _speech.startStreaming();
      _coachSocket?.startAudioInput(sampleRate: 16000);
      _micSub = stream.listen(
        (chunk) {
          _coachSocket?.sendAudioChunk(chunk);
        },
        onError: (_) {
          if (!mounted) return;
          setState(() {
            _recording = false;
            _processing = false;
            _messages.add(const _ChatMessage(
                sender: 'Aura',
                text:
                    'I lost connection to the server. Please check your internet and tap the microphone to try again.',
                isAura: true));
          });
          state.setVoiceState(VoiceState.idle);
        },
      );

      _silenceTimer?.cancel();
      _silenceTimer = null;
      _ampSub = _speech.getAmplitudeStream().listen((amp) {
        if (!mounted || !_recording) return;

        // Barge-in: skip remaining TTS if user starts speaking
        if (_playingAssistantAudio && amp.current > -30.0) {
          _assistantAudioQueue.clear();
          _speech.stopPlayback();
          _playingAssistantAudio = false;
        }

        if (amp.current < -38.0) {
          _silenceTimer ??= Timer(const Duration(milliseconds: 2500), () {
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
        _voiceInputArmed = true;
        _voiceNotice = null;
        _recording = true;
        _partialTranscript = null;
      });
      state.setVoiceState(VoiceState.listening, text: 'Listening…');
    } catch (e) {
      final message = _microphoneErrorMessage(e);
      _setVoiceNotice(message);
      if (!silentOnError) {
        _addMessage('Aura', message, isAura: true);
      }
      // silentOnError: auto-start quietly fails, user can tap mic manually.
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final voiceState = state.voiceState;

    String avatarState = 'idle';
    if (voiceState == VoiceState.speaking) avatarState = 'speaking';
    if (voiceState == VoiceState.listening) avatarState = 'listening';
    if (voiceState == VoiceState.analyzing) avatarState = 'analyzing';

    final isDisconnected = _socketStatus == 'Disconnected';
    final showAudioUnlockOverlay = !_audioUnlocked &&
        (_assistantAudioQueue.isNotEmpty || _voiceNotice != null);

    Color badgeColor = isDisconnected ? AuraColors.error : AuraColors.primary;
    String badgeText =
        state.statusText.isEmpty ? _socketStatus : state.statusText;
    if (voiceState == VoiceState.listening) {
      badgeColor = const Color(0xFF22C55E);
    }
    if (voiceState == VoiceState.analyzing) {
      badgeColor = const Color(0xFFF59E0B);
    }

    final bootstrap = state.coachBootstrap;
    final classification = state.classification;

    return Container(
      decoration: const BoxDecoration(gradient: AuraColors.backgroundGradient),
      child: SafeArea(
        child: Builder(
          builder: (context) {
            final state = context.read<AppState>();
            return Listener(
              behavior: HitTestBehavior.translucent,
              onPointerDown: (_) {
                unawaited(_handleUserAudioUnlock(state));
              },
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final isCompact = constraints.maxWidth < 760;
                  final horizontalPadding = isCompact ? 14.0 : 20.0;
                  final voiceBannerMessage = _voiceBannerMessage();

                  return Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 1040),
                      child: Column(
                        children: [
                          Padding(
                            padding: EdgeInsets.symmetric(
                              horizontal: horizontalPadding,
                              vertical: 14,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    const Expanded(
                                      child: Text(
                                        'Aura Coach',
                                        style: TextStyle(
                                          fontSize: 20,
                                          fontWeight: FontWeight.w800,
                                          color: AuraColors.textPrimary,
                                          letterSpacing: -0.5,
                                        ),
                                      ),
                                    ),
                                    IconButton(
                                      onPressed: () =>
                                          context.read<AppState>().logout(),
                                      icon: const Icon(
                                        Icons.logout_rounded,
                                        color: AuraColors.textSecondary,
                                      ),
                                    ),
                                  ],
                                ),
                                Row(
                                  children: [
                                    _buildLevelSelector(),
                                    const Spacer(),
                                    if (isDisconnected)
                                      TextButton.icon(
                                        onPressed: _connectCoachSocket,
                                        icon: const Icon(Icons.refresh_rounded,
                                            size: 16),
                                        label: const Text('Retry',
                                            style: TextStyle(fontSize: 12)),
                                        style: TextButton.styleFrom(
                                          foregroundColor: AuraColors.error,
                                          visualDensity: VisualDensity.compact,
                                        ),
                                      ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                          Stack(
                            alignment: Alignment.center,
                            children: [
                              AuraAvatar(
                                state: avatarState,
                                size: isCompact ? 108 : 150,
                              ),
                              if (showAudioUnlockOverlay)
                                Positioned.fill(
                                  child: GestureDetector(
                                    onTap: () => _handleUserAudioUnlock(state),
                                    child: Container(
                                      decoration: BoxDecoration(
                                        color:
                                            Colors.black.withValues(alpha: 0.4),
                                        shape: BoxShape.circle,
                                      ),
                                      child: Column(
                                        mainAxisAlignment:
                                            MainAxisAlignment.center,
                                        children: [
                                          const Icon(Icons.play_arrow_rounded,
                                              color: Colors.white, size: 40),
                                          const SizedBox(height: 4),
                                          Text(
                                            'START',
                                            style: GoogleFonts.spaceGrotesk(
                                              color: Colors.white,
                                              fontSize: 10,
                                              fontWeight: FontWeight.w800,
                                              letterSpacing: 2,
                                            ),
                                          ),
                                        ],
                                      ),
                                    ).animate().scale(
                                        duration: 400.ms,
                                        curve: Curves.elasticOut),
                                  ),
                                ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          Padding(
                            padding: EdgeInsets.symmetric(
                                horizontal: horizontalPadding),
                            child: Row(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.theater_comedy_rounded,
                                    size: 14, color: AuraColors.textSecondary),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: DropdownButtonHideUnderline(
                                    child: DropdownButton<String>(
                                      value: state.preferredScenario,
                                      isDense: true,
                                      dropdownColor: AuraColors.surfaceDark,
                                      icon: const Icon(
                                          Icons.arrow_drop_down_rounded,
                                          color: AuraColors.textSecondary),
                                      style: GoogleFonts.spaceGrotesk(
                                        color: AuraColors.textSecondary,
                                        fontSize: 12,
                                        fontWeight: FontWeight.w600,
                                      ),
                                      items: [
                                        'General conversation',
                                        'Job interview',
                                        'Grocery store',
                                        'Travel & Airport',
                                        'Restaurant ordering',
                                        'Medical appointment',
                                        'Technical discussion',
                                      ]
                                          .map((s) => DropdownMenuItem(
                                              value: s, child: Text(s)))
                                          .toList(),
                                      onChanged: (val) {
                                        if (val != null) {
                                          state.selectScenario(val);
                                          _coachSocket?.requestBootstrap();
                                        }
                                      },
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 8),
                          AuraStatusBadge(text: badgeText, color: badgeColor),
                          if (voiceBannerMessage != null) ...[
                            const SizedBox(height: 12),
                            Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal: horizontalPadding,
                              ),
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
                                      color:
                                          _browserVoice.blockingReason != null
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
                          ],
                          const SizedBox(height: 14),
                          if (bootstrap != null)
                            Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal: horizontalPadding,
                              ),
                              child: GlassCard(
                                padding: EdgeInsets.all(isCompact ? 12 : 16),
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        Expanded(
                                          child: Text(
                                            bootstrap.needsOnboarding
                                                ? 'Coach placement'
                                                : 'Coach assessment',
                                            style: GoogleFonts.spaceGrotesk(
                                              fontWeight: FontWeight.w700,
                                              color: AuraColors.textPrimary,
                                            ),
                                          ),
                                        ),
                                        if (classification != null)
                                          _InfoChip(
                                            label: classification.standing
                                                .replaceAll('_', ' '),
                                          ),
                                      ],
                                    ),
                                    const SizedBox(height: 8),
                                    Text(
                                      bootstrap.spokenProgressSummary,
                                      maxLines:
                                          isCompact && !_showBootstrapDetails
                                              ? 3
                                              : 5,
                                      overflow:
                                          isCompact && !_showBootstrapDetails
                                              ? TextOverflow.ellipsis
                                              : TextOverflow.visible,
                                      style: GoogleFonts.spaceGrotesk(
                                        color: AuraColors.textSecondary,
                                        fontSize: isCompact ? 11.5 : 12,
                                        height: 1.4,
                                      ),
                                    ),
                                    if (classification != null &&
                                        (!isCompact ||
                                            _showBootstrapDetails)) ...[
                                      const SizedBox(height: 10),
                                      Wrap(
                                        spacing: 8,
                                        runSpacing: 8,
                                        children: [
                                          _InfoChip(
                                            label: classification.passStatus
                                                .replaceAll('_', ' '),
                                          ),
                                          if (classification
                                              .improvementFocus.isNotEmpty)
                                            _InfoChip(
                                              label:
                                                  'focus: ${classification.improvementFocus.first}',
                                            ),
                                        ],
                                      ),
                                    ],
                                    if (isCompact) ...[
                                      const SizedBox(height: 8),
                                      Align(
                                        alignment: Alignment.centerLeft,
                                        child: TextButton(
                                          onPressed: () {
                                            setState(() {
                                              _showBootstrapDetails =
                                                  !_showBootstrapDetails;
                                            });
                                          },
                                          style: TextButton.styleFrom(
                                            padding: const EdgeInsets.symmetric(
                                              horizontal: 0,
                                              vertical: 4,
                                            ),
                                            minimumSize: Size.zero,
                                            tapTargetSize: MaterialTapTargetSize
                                                .shrinkWrap,
                                          ),
                                          child: Text(
                                            _showBootstrapDetails
                                                ? 'Hide details'
                                                : 'Show details',
                                            style: GoogleFonts.spaceGrotesk(
                                              color: AuraColors.primary,
                                              fontSize: 12,
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                        ),
                                      ),
                                    ],
                                  ],
                                ),
                              ),
                            ).animate().fadeIn(duration: 250.ms),
                          if (_partialTranscript != null &&
                              _partialTranscript!.trim().isNotEmpty)
                            Padding(
                              padding: EdgeInsets.symmetric(
                                horizontal: horizontalPadding,
                                vertical: 8,
                              ),
                              child: GlassCard(
                                padding: EdgeInsets.all(isCompact ? 14 : 16),
                                child: Row(
                                  children: [
                                    const Icon(
                                      Icons.hearing_rounded,
                                      color: AuraColors.primary,
                                      size: 24,
                                    )
                                        .animate(
                                            onPlay: (c) =>
                                                c.repeat(reverse: true))
                                        .scaleXY(end: 1.2, duration: 400.ms),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: Text(
                                        _partialTranscript!,
                                        style: GoogleFonts.spaceGrotesk(
                                          color: AuraColors.textPrimary,
                                          fontSize: isCompact ? 14 : 16,
                                          fontWeight: FontWeight.w600,
                                          height: 1.4,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          SizedBox(height: isCompact ? 8 : 12),
                          Expanded(
                            child: ListView.builder(
                              controller: _scroll,
                              padding: EdgeInsets.symmetric(
                                horizontal: isCompact ? 12 : 16,
                              ),
                              physics: const BouncingScrollPhysics(),
                              itemCount: _messages.length,
                              itemBuilder: (_, i) =>
                                  _ChatBubble(msg: _messages[i]),
                            ),
                          ),
                          AnimatedPadding(
                            duration: const Duration(milliseconds: 180),
                            curve: Curves.easeOut,
                            padding: EdgeInsets.fromLTRB(
                              horizontalPadding,
                              8,
                              horizontalPadding,
                              16 +
                                  MediaQuery.of(context).viewInsets.bottom +
                                  MediaQuery.of(context).viewPadding.bottom,
                            ),
                            child: Column(
                              children: [
                                GlassCard(
                                  padding: EdgeInsets.all(isCompact ? 12 : 14),
                                  child: isCompact
                                      ? Column(
                                          children: [
                                            TextField(
                                              controller: _textController,
                                              style: const TextStyle(
                                                color: Colors.white,
                                                fontSize: 14,
                                              ),
                                              decoration: InputDecoration(
                                                hintText: 'Type a reply',
                                                hintStyle: TextStyle(
                                                  color:
                                                      Colors.white.withValues(
                                                    alpha: 0.5,
                                                  ),
                                                  fontSize: 13,
                                                ),
                                                filled: true,
                                                fillColor:
                                                    Colors.white.withValues(
                                                  alpha: 0.08,
                                                ),
                                                contentPadding:
                                                    const EdgeInsets.symmetric(
                                                  horizontal: 16,
                                                  vertical: 12,
                                                ),
                                                border: OutlineInputBorder(
                                                  borderRadius:
                                                      BorderRadius.circular(18),
                                                  borderSide: BorderSide.none,
                                                ),
                                              ),
                                              textInputAction:
                                                  TextInputAction.send,
                                              onSubmitted: (_) =>
                                                  _sendTypedReply(),
                                            ),
                                            const SizedBox(height: 12),
                                            SizedBox(
                                              width: double.infinity,
                                              child: ElevatedButton.icon(
                                                onPressed: _sendTypedReply,
                                                icon: const Icon(
                                                    Icons.send_rounded),
                                                label: const Text('Send reply'),
                                              ),
                                            ),
                                          ],
                                        )
                                      : Row(
                                          children: [
                                            Expanded(
                                              child: TextField(
                                                controller: _textController,
                                                style: const TextStyle(
                                                  color: Colors.white,
                                                  fontSize: 14,
                                                ),
                                                decoration: InputDecoration(
                                                  hintText: 'Type a reply',
                                                  hintStyle: TextStyle(
                                                    color:
                                                        Colors.white.withValues(
                                                      alpha: 0.5,
                                                    ),
                                                    fontSize: 13,
                                                  ),
                                                  filled: true,
                                                  fillColor:
                                                      Colors.white.withValues(
                                                    alpha: 0.08,
                                                  ),
                                                  contentPadding:
                                                      const EdgeInsets
                                                          .symmetric(
                                                    horizontal: 16,
                                                    vertical: 12,
                                                  ),
                                                  border: OutlineInputBorder(
                                                    borderRadius:
                                                        BorderRadius.circular(
                                                            18),
                                                    borderSide: BorderSide.none,
                                                  ),
                                                ),
                                                textInputAction:
                                                    TextInputAction.send,
                                                onSubmitted: (_) =>
                                                    _sendTypedReply(),
                                              ),
                                            ),
                                            const SizedBox(width: 10),
                                            ElevatedButton.icon(
                                              onPressed: _sendTypedReply,
                                              icon: const Icon(
                                                  Icons.send_rounded),
                                              label: const Text('Send'),
                                            ),
                                          ],
                                        ),
                                ),
                                const SizedBox(height: 14),
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
                  );
                },
              ),
            );
          },
        ),
      ),
    );
  }
}

class _InfoChip extends StatelessWidget {
  const _InfoChip({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: AuraColors.primary.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AuraColors.primary.withValues(alpha: 0.3)),
      ),
      child: Text(
        label,
        style: GoogleFonts.spaceGrotesk(
          color: AuraColors.primary,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class _ChatMessage {
  const _ChatMessage({
    required this.sender,
    required this.text,
    required this.isAura,
    this.fillerWords = 0,
    this.totalWords = 0,
    this.lexicalDiversity = 0.0,
  });

  final String sender;
  final String text;
  final bool isAura;
  final int fillerWords;
  final int totalWords;
  final double lexicalDiversity;
}

class _ChatBubble extends StatelessWidget {
  const _ChatBubble({required this.msg});

  final _ChatMessage msg;

  @override
  Widget build(BuildContext context) {
    final screenWidth = MediaQuery.of(context).size.width;
    final maxBubbleWidth = screenWidth < 640 ? screenWidth * 0.82 : 380.0;

    return Align(
      alignment: msg.isAura ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: EdgeInsets.symmetric(
            horizontal: screenWidth < 400 ? 12 : 14, vertical: 10),
        constraints: BoxConstraints(maxWidth: maxBubbleWidth),
        decoration: BoxDecoration(
          color: msg.isAura
              ? AuraColors.cardDark
              : AuraColors.primary.withValues(alpha: 0.14),
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: msg.isAura
                ? AuraColors.borderDark
                : AuraColors.primary.withValues(alpha: 0.25),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 6,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text(
                  msg.sender,
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: msg.isAura
                        ? AuraColors.primary
                        : AuraColors.textPrimary,
                  ),
                ),
                if (!msg.isAura && msg.fillerWords > 0)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.orange.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: Colors.orange.withValues(alpha: 0.5),
                      ),
                    ),
                    child: Text(
                      '${msg.fillerWords} filler',
                      style: GoogleFonts.spaceGrotesk(
                          fontSize: 9,
                          color: Colors.orange,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
                if (!msg.isAura && msg.lexicalDiversity > 0)
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.blue.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(4),
                      border: Border.all(
                        color: Colors.blue.withValues(alpha: 0.5),
                      ),
                    ),
                    child: Text(
                      'Lex: ${msg.lexicalDiversity.toStringAsFixed(2)}',
                      style: GoogleFonts.spaceGrotesk(
                          fontSize: 9,
                          color: Colors.blue,
                          fontWeight: FontWeight.bold),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              msg.text,
              style: GoogleFonts.spaceGrotesk(
                fontSize: 14,
                color: AuraColors.textPrimary,
                height: 1.4,
              ),
            ),
          ],
        ),
      ).animate().fadeIn(duration: 250.ms).slideY(begin: 0.12),
    );
  }
}
