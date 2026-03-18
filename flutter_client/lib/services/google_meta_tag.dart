import 'package:web/web.dart' as web;

void configureGoogleSignInMetaTag(String clientId) {
  final trimmedClientId = clientId.trim();
  if (trimmedClientId.isEmpty) {
    return;
  }

  final existing =
      web.document.head?.querySelector('meta[name="google-signin-client_id"]');
  final metaElement = existing != null
      ? existing as web.HTMLMetaElement
      : web.document.createElement('meta') as web.HTMLMetaElement;

  metaElement.name = 'google-signin-client_id';
  metaElement.content = trimmedClientId;

  if (existing == null) {
    web.document.head?.append(metaElement);
  }
}
