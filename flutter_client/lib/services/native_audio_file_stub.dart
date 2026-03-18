import 'dart:typed_data';

Future<String> persistAudioBytesToTempFile(
  Uint8List bytes, {
  required String extension,
}) async {
  throw UnsupportedError('Temporary native audio files are not supported.');
}

Future<void> deletePersistedAudioFile(String path) async {}
