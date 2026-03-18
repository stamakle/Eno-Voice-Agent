import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';
import '../models/api_models.dart';
import '../services/api_client.dart';
import '../services/google_meta_tag.dart'
    if (dart.library.io) '../services/google_meta_tag_stub.dart';

enum VoiceState { idle, speaking, listening, analyzing }

class AppState extends ChangeNotifier {
  AppState() {
    _init();
  }

  final ApiClient _api = ApiClient();
  final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  StreamSubscription<GoogleSignInAuthenticationEvent>? _googleAuthSubscription;

  String? authToken;
  String? refreshToken;
  AuthUserModel? currentUser;
  bool authRequiresVerifiedEmail = false;
  bool verificationRequired = false;
  String? debugVerificationToken;
  String? authNotice;
  String learnerId = '';
  String displayName = 'Learner';
  String levelBand = 'beginner';
  String levelLabel = 'beginner';
  String preferredScenario = 'General conversation';
  int totalCompleted = 0;
  int reviewCountDue = 0;
  List<String> weakTopics = [];
  List<CourseTemplateSummary> templates = [];
  DashboardSummary? dashboard;
  bool loading = true;
  bool backendOnline = false;
  bool googleAuthEnabled = false;
  bool googleSignInReady = false;
  bool googleSignInInProgress = false;
  String? googleSignInError;
  String statusText = '';
  VoiceState voiceState = VoiceState.idle;
  CoachBootstrapModel? coachBootstrap;

  Future<void> _init() async {
    await _initializeGoogleSignIn();
    final prefs = await SharedPreferences.getInstance();
    authToken = prefs.getString('auth_token');
    refreshToken = prefs.getString('refresh_token');
    await refresh();
  }

  bool get isAuthenticated =>
      authToken != null && authToken!.isNotEmpty && currentUser != null;
  bool get needsOnboarding => coachBootstrap?.needsOnboarding ?? false;
  bool get hasResumeLesson => coachBootstrap?.hasResumeLesson ?? false;
  NextLessonSelectionModel? get recommendedLesson =>
      coachBootstrap?.recommendedLesson;
  String? get recommendedLessonTitle => coachBootstrap?.recommendedLessonTitle;
  CoachClassificationModel? get classification =>
      coachBootstrap?.classification;
  bool get canUseGoogleSignIn => googleAuthEnabled && googleSignInReady;

  Future<void> refresh() async {
    loading = true;
    notifyListeners();

    try {
      final health = await _api.health();
      backendOnline = health['status'] == 'ok';
      authRequiresVerifiedEmail =
          (health['auth_requires_verified_email'] as String? ?? 'false') ==
              'true';
      googleAuthEnabled =
          (health['google_auth_enabled'] as String? ?? 'false') == 'true';
      if (backendOnline && authToken != null && authToken!.isNotEmpty) {
        try {
          currentUser = await _api.me(authToken!);
          learnerId = currentUser!.learnerId;
          displayName = currentUser!.displayName;
          verificationRequired =
              authRequiresVerifiedEmail && !currentUser!.emailVerified;
          if (!verificationRequired) {
            final bootstrap = await _api.fetchCoachBootstrap(authToken!);
            applyCoachBootstrap(bootstrap);
          } else {
            coachBootstrap = null;
          }
        } catch (_) {
          final refreshed = await _tryRefresh();
          if (refreshed) {
            currentUser = await _api.me(authToken!);
            learnerId = currentUser!.learnerId;
            displayName = currentUser!.displayName;
            verificationRequired =
                authRequiresVerifiedEmail && !currentUser!.emailVerified;
            if (!verificationRequired) {
              final bootstrap = await _api.fetchCoachBootstrap(authToken!);
              applyCoachBootstrap(bootstrap);
            } else {
              coachBootstrap = null;
            }
          } else {
            await clearAuth(notify: false);
          }
        }
      }
    } catch (_) {
      backendOnline = false;
      googleAuthEnabled = false;
    }

    loading = false;
    notifyListeners();
  }

  Future<void> register(
      {required String email,
      required String password,
      required String displayName}) async {
    final session = await _api.register(
        email: email, password: password, displayName: displayName);
    await _applyAuthSession(session);
  }

  Future<void> login({required String email, required String password}) async {
    final session = await _api.login(email: email, password: password);
    await _applyAuthSession(session);
  }

  Future<void> signInWithGoogle() async {
    clearGoogleSignInError(notify: false);
    if (!canUseGoogleSignIn) {
      throw ApiException('Google sign-in is not configured for this build.');
    }
    if (!_googleSignIn.supportsAuthenticate()) {
      return;
    }
    googleSignInInProgress = true;
    notifyListeners();
    try {
      await _googleSignIn.authenticate();
    } catch (error) {
      googleSignInInProgress = false;
      googleSignInError = _googleSignInMessage(error);
      notifyListeners();
      rethrow;
    }
  }

  Future<void> logout() async {
    final token = authToken;
    if (token != null && token.isNotEmpty) {
      await _api.logout(token);
    }
    if (googleSignInReady) {
      try {
        await _googleSignIn.signOut();
      } catch (_) {}
    }
    await clearAuth();
  }

  Future<void> _applyAuthSession(AuthSessionModel session) async {
    authToken = session.token;
    refreshToken = session.refreshToken;
    currentUser = session.user;
    verificationRequired = session.emailVerificationRequired;
    debugVerificationToken = session.debugEmailVerificationToken;
    authNotice = session.emailVerificationRequired
        ? 'Check your verification email before using the coach.'
        : null;
    learnerId = session.user.learnerId;
    displayName = session.user.displayName;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('auth_token', session.token);
    await prefs.setString('refresh_token', session.refreshToken);
    await refresh();
  }

  Future<void> clearAuth({bool notify = true}) async {
    authToken = null;
    refreshToken = null;
    currentUser = null;
    learnerId = '';
    displayName = 'Learner';
    preferredScenario = 'General conversation';
    coachBootstrap = null;
    dashboard = null;
    verificationRequired = false;
    debugVerificationToken = null;
    authNotice = null;
    googleSignInError = null;
    googleSignInInProgress = false;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('auth_token');
    await prefs.remove('refresh_token');
    if (notify) {
      notifyListeners();
    }
  }

  Future<bool> _tryRefresh() async {
    final token = refreshToken;
    if (token == null || token.isEmpty) {
      return false;
    }
    try {
      final session = await _api.refresh(token);
      authToken = session.token;
      refreshToken = session.refreshToken;
      currentUser = session.user;
      verificationRequired = session.emailVerificationRequired;
      debugVerificationToken = session.debugEmailVerificationToken;
      learnerId = session.user.learnerId;
      displayName = session.user.displayName;
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('auth_token', session.token);
      await prefs.setString('refresh_token', session.refreshToken);
      return true;
    } catch (_) {
      return false;
    }
  }

  void applyCoachBootstrap(CoachBootstrapModel bootstrap) {
    coachBootstrap = bootstrap;
    learnerId = bootstrap.learnerId;
    displayName = bootstrap.displayName;
    levelBand = bootstrap.levelBand;
    levelLabel = bootstrap.levelLabel;
    preferredScenario = bootstrap.preferredScenario;
    totalCompleted = bootstrap.totalCompletedLessons;
    reviewCountDue = bootstrap.reviewCountDue;
    weakTopics = bootstrap.weakTopics;
  }

  Future<void> resendVerification(String email) async {
    final response = await _api.resendVerification(email);
    authNotice = response.message;
    debugVerificationToken = response.debugToken ?? debugVerificationToken;
    notifyListeners();
  }

  Future<void> verifyEmail(String token) async {
    final response = await _api.verifyEmail(token);
    authNotice = response.message;
    debugVerificationToken = null;
    await refresh();
  }

  Future<void> requestPasswordReset(String email) async {
    final response = await _api.requestPasswordReset(email);
    authNotice = response.message;
    debugVerificationToken = response.debugToken ?? debugVerificationToken;
    notifyListeners();
  }

  Future<void> confirmPasswordReset({
    required String token,
    required String newPassword,
  }) async {
    final response =
        await _api.confirmPasswordReset(token: token, newPassword: newPassword);
    authNotice = response.message;
    notifyListeners();
  }

  Future<void> selectLevel(String level) async {
    if (!isAuthenticated) {
      return;
    }
    try {
      await _api.updateProfile(token: authToken!, levelBand: level);
      levelBand = level;
    } catch (_) {}
    await refresh();
  }

  Future<void> selectScenario(String scenario) async {
    if (!isAuthenticated) {
      return;
    }
    try {
      await _api.updateProfile(token: authToken!, preferredScenario: scenario);
    } catch (_) {}
    await refresh();
  }

  Future<void> completeOnboarding() async {
    await refresh();
  }

  void clearGoogleSignInError({bool notify = true}) {
    googleSignInError = null;
    if (notify) {
      notifyListeners();
    }
  }

  void setVoiceState(VoiceState state, {String text = ''}) {
    voiceState = state;
    statusText = text;
    notifyListeners();
  }

  Future<void> _initializeGoogleSignIn() async {
    if (!AppConfig.googleSignInConfigured) {
      return;
    }

    try {
      configureGoogleSignInMetaTag(AppConfig.googleWebClientId);
      await _googleSignIn.initialize(
        clientId: AppConfig.googleWebClientId.isEmpty
            ? null
            : AppConfig.googleWebClientId,
        serverClientId: AppConfig.googleServerClientId.isEmpty
            ? null
            : AppConfig.googleServerClientId,
      );
      _googleAuthSubscription = _googleSignIn.authenticationEvents.listen((
        event,
      ) {
        unawaited(_handleGoogleAuthenticationEvent(event));
      });
      _googleAuthSubscription!.onError(_handleGoogleAuthenticationError);
      googleSignInReady = true;
      googleSignInError = null;
    } catch (error) {
      googleSignInReady = false;
      googleSignInError = _googleSignInMessage(error);
    }
  }

  Future<void> _handleGoogleAuthenticationEvent(
    GoogleSignInAuthenticationEvent event,
  ) async {
    switch (event) {
      case GoogleSignInAuthenticationEventSignIn():
        final idToken = event.user.authentication.idToken;
        if (idToken == null || idToken.isEmpty) {
          googleSignInInProgress = false;
          googleSignInError =
              'Google did not return an identity token for this session.';
          notifyListeners();
          return;
        }

        googleSignInInProgress = true;
        googleSignInError = null;
        notifyListeners();
        try {
          final session = await _api.loginWithGoogle(idToken: idToken);
          await _applyAuthSession(session);
        } catch (error) {
          googleSignInError = error is ApiException
              ? error.message
              : _googleSignInMessage(error);
        } finally {
          googleSignInInProgress = false;
          notifyListeners();
        }
      case GoogleSignInAuthenticationEventSignOut():
        googleSignInInProgress = false;
        notifyListeners();
    }
  }

  void _handleGoogleAuthenticationError(Object error) {
    googleSignInInProgress = false;
    googleSignInError = _googleSignInMessage(error);
    notifyListeners();
  }

  String _googleSignInMessage(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    if (error is GoogleSignInException) {
      switch (error.code) {
        case GoogleSignInExceptionCode.canceled:
          return 'Google sign-in was canceled.';
        case GoogleSignInExceptionCode.clientConfigurationError:
        case GoogleSignInExceptionCode.providerConfigurationError:
          return 'Google sign-in is configured incorrectly for this build.';
        case GoogleSignInExceptionCode.uiUnavailable:
          return 'Google sign-in UI is unavailable right now.';
        case GoogleSignInExceptionCode.interrupted:
          return 'Google sign-in was interrupted. Try again.';
        default:
          return error.description ?? 'Google sign-in failed.';
      }
    }
    return 'Google sign-in failed.';
  }

  @override
  void dispose() {
    _googleAuthSubscription?.cancel();
    super.dispose();
  }
}
