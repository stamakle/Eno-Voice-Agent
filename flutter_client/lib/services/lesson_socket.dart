import 'dart:convert';
import 'dart:typed_data';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/app_config.dart';

class LessonSocket {
  LessonSocket({required String token})
      : channel = WebSocketChannel.connect(
          Uri.parse('${AppConfig.lessonWebSocketUrl}?token=${Uri.encodeQueryComponent(token)}'),
        );

  final WebSocketChannel channel;

  Stream<Map<String, dynamic>> get stream =>
      channel.stream.map((dynamic event) => jsonDecode(event as String) as Map<String, dynamic>);

  void joinLesson({
    required String courseId,
    required String chapterId,
    required String lessonId,
  }) {
    _send(<String, dynamic>{
      'type': 'join_lesson',
      'course_id': courseId,
      'chapter_id': chapterId,
      'lesson_id': lessonId,
    });
  }

  void startAudioInput({int sampleRate = 16000}) {
    _send(<String, dynamic>{
      'type': 'audio_input_start',
      'sample_rate': sampleRate,
    });
  }

  void sendAudioChunk(Uint8List data) {
    _send(<String, dynamic>{
      'type': 'audio_chunk',
      'data': base64Encode(data),
    });
  }

  void commitAudioInput() {
    _send(<String, dynamic>{'type': 'audio_commit'});
  }

  void sendLearnerText(String text) {
    _send(<String, dynamic>{'type': 'learner_text', 'text': text});
  }

  void requestState() {
    _send(<String, dynamic>{'type': 'request_state'});
  }

  void completeLesson({
    List<String> notes = const <String>[],
    List<String> weakTopics = const <String>[],
  }) {
    _send(<String, dynamic>{
      'type': 'complete_lesson',
      'notes': notes,
      'weak_topics': weakTopics,
    });
  }

  void dispose() {
    channel.sink.close();
  }

  void _send(Map<String, dynamic> payload) {
    channel.sink.add(jsonEncode(payload));
  }
}
