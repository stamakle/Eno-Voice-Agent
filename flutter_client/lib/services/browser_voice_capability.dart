// ignore_for_file: avoid_web_libraries_in_flutter

import 'package:web/web.dart' as web;

class BrowserVoiceCapability {
  const BrowserVoiceCapability({
    required this.isWebPlatform,
    required this.supportsMicrophoneCapture,
    required this.canCaptureMicrophone,
    required this.requiresSecureContext,
    required this.isProbablyMobile,
    required this.needsUserGestureForAudio,
    this.blockingReason,
  });

  final bool isWebPlatform;
  final bool supportsMicrophoneCapture;
  final bool canCaptureMicrophone;
  final bool requiresSecureContext;
  final bool isProbablyMobile;
  final bool needsUserGestureForAudio;
  final String? blockingReason;
}

BrowserVoiceCapability getBrowserVoiceCapability() {
  final hostname = web.window.location.hostname;
  final isLoopback =
      hostname == 'localhost' || hostname == '127.0.0.1' || hostname == '::1';
  final isSecureContext = web.window.isSecureContext;
  final userAgent = web.window.navigator.userAgent.toLowerCase();
  final isProbablyMobile = RegExp(
    r'android|iphone|ipad|ipod|mobile|silk|kindle|opera mini',
  ).hasMatch(userAgent);

  if (!isSecureContext && !isLoopback) {
    return BrowserVoiceCapability(
      isWebPlatform: true,
      supportsMicrophoneCapture: true,
      canCaptureMicrophone: false,
      requiresSecureContext: true,
      isProbablyMobile: isProbablyMobile,
      needsUserGestureForAudio: true,
      blockingReason:
          'Voice input needs HTTPS on this device. Open the app over trusted HTTPS to use the microphone.',
    );
  }

  return BrowserVoiceCapability(
    isWebPlatform: true,
    supportsMicrophoneCapture: true,
    canCaptureMicrophone: true,
    requiresSecureContext: false,
    isProbablyMobile: isProbablyMobile,
    needsUserGestureForAudio: true,
  );
}
