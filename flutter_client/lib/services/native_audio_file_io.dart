import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

Future<String> persistAudioBytesToTempFile(
  Uint8List bytes, {
  required String extension,
}) async {
  final tempDir = await getTemporaryDirectory();
  final file = File(
    '${tempDir.path}/aura_audio_${DateTime.now().microsecondsSinceEpoch}.$extension',
  );
  await file.writeAsBytes(bytes, flush: true);
  return file.path;
}

Future<void> deletePersistedAudioFile(String path) async {
  final file = File(path);
  if (await file.exists()) {
    await file.delete();
  }
}
