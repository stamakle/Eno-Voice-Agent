import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static String get apiBaseUrl {
    const fromEnv =
        String.fromEnvironment('ENGLISH_TECH_API_BASE_URL', defaultValue: '');
    return fromEnv.isNotEmpty
        ? fromEnv
        : (dotenv.env['ENGLISH_TECH_API_BASE_URL'] ?? 'http://127.0.0.1:8091');
  }

  static String get lessonWebSocketUrl {
    const fromEnv =
        String.fromEnvironment('ENGLISH_TECH_LESSON_WS_URL', defaultValue: '');
    return fromEnv.isNotEmpty
        ? fromEnv
        : (dotenv.env['ENGLISH_TECH_LESSON_WS_URL'] ??
            'ws://127.0.0.1:8091/ws/lesson');
  }

  static String get coachWebSocketUrl {
    const fromEnv =
        String.fromEnvironment('ENGLISH_TECH_COACH_WS_URL', defaultValue: '');
    return fromEnv.isNotEmpty
        ? fromEnv
        : (dotenv.env['ENGLISH_TECH_COACH_WS_URL'] ??
            'ws://127.0.0.1:8091/api/coach/ws/coach');
  }

  static String get googleWebClientId {
    const fromEnv = String.fromEnvironment(
      'ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID',
      defaultValue: '',
    );
    return fromEnv.isNotEmpty
        ? fromEnv
        : (dotenv.env['ENGLISH_TECH_GOOGLE_WEB_CLIENT_ID'] ?? '');
  }

  static String get googleServerClientId {
    const fromEnv = String.fromEnvironment(
      'ENGLISH_TECH_GOOGLE_SERVER_CLIENT_ID',
      defaultValue: '',
    );
    return fromEnv.isNotEmpty
        ? fromEnv
        : (dotenv.env['ENGLISH_TECH_GOOGLE_SERVER_CLIENT_ID'] ?? '');
  }

  static bool get googleSignInConfigured =>
      googleWebClientId.isNotEmpty || googleServerClientId.isNotEmpty;
}
