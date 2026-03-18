import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import '../models/api_models.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.rawBody});

  final String message;
  final int? statusCode;
  final String? rawBody;

  @override
  String toString() => message;
}

class ApiClient {
  Future<http.Response> _send(Future<http.Response> Function() request) async {
    try {
      return await request();
    } on ApiException {
      rethrow;
    } on Exception {
      throw ApiException(
        'Cannot reach the backend at ${AppConfig.apiBaseUrl}. Start the API server and try again.',
      );
    }
  }

  String _extractErrorMessage(http.Response response) {
    if (response.body.isNotEmpty) {
      try {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          final detail = decoded['detail'];
          if (detail is String && detail.trim().isNotEmpty) {
            return detail.trim();
          }
          if (detail is List) {
            final messages = detail
                .map((item) {
                  if (item is Map<String, dynamic>) {
                    final itemMessage = item['msg'];
                    if (itemMessage is String &&
                        itemMessage.trim().isNotEmpty) {
                      return itemMessage.trim();
                    }
                  }
                  return null;
                })
                .whereType<String>()
                .toList();
            if (messages.isNotEmpty) {
              return messages.join(' ');
            }
          }
          final message = decoded['message'];
          if (message is String && message.trim().isNotEmpty) {
            return message.trim();
          }
        }
      } on FormatException {
        // Fall back to generic status-specific messaging below.
      }
    }

    if (response.statusCode >= 500) {
      return 'The server hit an internal error. Check that the backend schema is up to date and try again.';
    }
    if (response.statusCode == 404) {
      return 'The requested API route was not found. Check that the backend is running the current code.';
    }
    return 'Request failed with status ${response.statusCode}.';
  }

  Map<String, dynamic> _decodeJson(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        _extractErrorMessage(response),
        statusCode: response.statusCode,
        rawBody: response.body,
      );
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Map<String, String> _headers({String? token, bool json = false}) {
    final headers = <String, String>{};
    if (json) {
      headers['Content-Type'] = 'application/json';
    }
    if (token != null && token.isNotEmpty) {
      headers['Authorization'] = 'Bearer $token';
    }
    return headers;
  }

  Future<Map<String, dynamic>> health() async {
    final response = await _send(
        () => http.get(Uri.parse('${AppConfig.apiBaseUrl}/health')));
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<AuthSessionModel> register({
    required String email,
    required String password,
    required String displayName,
  }) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/register'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{
            'email': email,
            'password': password,
            'display_name': displayName,
          }),
        ));
    return AuthSessionModel.fromJson(_decodeJson(response));
  }

  Future<AuthSessionModel> login({
    required String email,
    required String password,
  }) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/login'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{
            'email': email,
            'password': password,
          }),
        ));
    return AuthSessionModel.fromJson(_decodeJson(response));
  }

  Future<AuthSessionModel> loginWithGoogle({
    required String idToken,
  }) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/google'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{
            'id_token': idToken,
          }),
        ));
    return AuthSessionModel.fromJson(_decodeJson(response));
  }

  Future<AuthUserModel> me(String token) async {
    final response = await _send(() => http.get(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/me'),
          headers: _headers(token: token),
        ));
    return AuthUserModel.fromJson(_decodeJson(response));
  }

  Future<AuthSessionModel> refresh(String refreshToken) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/refresh'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{'refresh_token': refreshToken}),
        ));
    return AuthSessionModel.fromJson(_decodeJson(response));
  }

  Future<void> logout(String token) async {
    await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/logout'),
          headers: _headers(token: token),
        ));
  }

  Future<AuthMessageModel> resendVerification(String email) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/resend-verification'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{'email': email}),
        ));
    return AuthMessageModel.fromJson(_decodeJson(response));
  }

  Future<AuthMessageModel> verifyEmail(String token) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/verify-email'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{'token': token}),
        ));
    return AuthMessageModel.fromJson(_decodeJson(response));
  }

  Future<AuthMessageModel> requestPasswordReset(String email) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/password-reset/request'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{'email': email}),
        ));
    return AuthMessageModel.fromJson(_decodeJson(response));
  }

  Future<AuthMessageModel> confirmPasswordReset({
    required String token,
    required String newPassword,
  }) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/password-reset/confirm'),
          headers: _headers(json: true),
          body: jsonEncode(<String, dynamic>{
            'token': token,
            'new_password': newPassword,
          }),
        ));
    return AuthMessageModel.fromJson(_decodeJson(response));
  }

  Future<List<AuthSessionSummaryModel>> listSessions(String token) async {
    final response = await _send(() => http.get(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/sessions'),
          headers: _headers(token: token),
        ));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        _extractErrorMessage(response),
        statusCode: response.statusCode,
        rawBody: response.body,
      );
    }
    final payload = jsonDecode(response.body) as List<dynamic>;
    return payload
        .map((item) =>
            AuthSessionSummaryModel.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<void> revokeSession({
    required String token,
    required String sessionId,
  }) async {
    final response = await _send(() => http.delete(
          Uri.parse('${AppConfig.apiBaseUrl}/api/auth/sessions/$sessionId'),
          headers: _headers(token: token),
        ));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        _extractErrorMessage(response),
        statusCode: response.statusCode,
        rawBody: response.body,
      );
    }
  }

  Future<List<CourseTemplateSummary>> fetchTemplates() async {
    final response = await _send(() => http
        .get(Uri.parse('${AppConfig.apiBaseUrl}/api/curriculum/templates')));
    final payload = jsonDecode(response.body) as List<dynamic>;
    return payload
        .map((item) =>
            CourseTemplateSummary.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<DashboardSummary> fetchDashboard(String token) async {
    final response = await _send(() => http.get(
          Uri.parse('${AppConfig.apiBaseUrl}/api/dashboard/me'),
          headers: _headers(token: token),
        ));
    return DashboardSummary.fromJson(_decodeJson(response));
  }

  Future<CoachBootstrapModel> fetchCoachBootstrap(String token) async {
    final response = await _send(() => http.get(
          Uri.parse('${AppConfig.apiBaseUrl}/api/coach/bootstrap'),
          headers: _headers(token: token),
        ));
    return CoachBootstrapModel.fromJson(_decodeJson(response));
  }

  Future<Map<String, dynamic>> completeLesson({
    required String token,
    required String learnerId,
    required String courseId,
    required String chapterId,
    required String lessonId,
    List<String> notes = const <String>[],
    List<String> weakTopics = const <String>[],
  }) async {
    final response = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/lesson/complete'),
          headers: _headers(token: token, json: true),
          body: jsonEncode(<String, dynamic>{
            'learner_id': learnerId,
            'lesson': <String, dynamic>{
              'course_id': courseId,
              'chapter_id': chapterId,
              'lesson_id': lessonId,
            },
            'completed': true,
            'notes': notes,
            'weak_topics': weakTopics,
          }),
        ));
    return _decodeJson(response);
  }

  Future<Map<String, dynamic>> updateProfile({
    required String token,
    String? levelBand,
    String? preferredScenario,
  }) async {
    final getResponse = await _send(() => http.get(
          Uri.parse('${AppConfig.apiBaseUrl}/api/profile/me'),
          headers: _headers(token: token),
        ));
    final profileData = _decodeJson(getResponse);

    if (levelBand != null) {
      profileData['level_band'] = levelBand;
      profileData['onboarding_completed'] = true;
    }

    if (preferredScenario != null) {
      profileData['preferred_scenario'] = preferredScenario;
    }

    final postResponse = await _send(() => http.post(
          Uri.parse('${AppConfig.apiBaseUrl}/api/profile/me'),
          headers: _headers(token: token, json: true),
          body: jsonEncode(profileData),
        ));
    return _decodeJson(postResponse);
  }
}
