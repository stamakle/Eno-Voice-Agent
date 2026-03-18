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
  return const BrowserVoiceCapability(
    isWebPlatform: false,
    supportsMicrophoneCapture: true,
    canCaptureMicrophone: true,
    requiresSecureContext: false,
    isProbablyMobile: false,
    needsUserGestureForAudio: false,
  );
}
