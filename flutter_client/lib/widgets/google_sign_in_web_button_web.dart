import 'package:flutter/widgets.dart';
import 'package:google_sign_in_web/web_only.dart' as google_web;

Widget buildGoogleSignInWebButton({double minimumWidth = 320}) {
  return google_web.renderButton(
    configuration: google_web.GSIButtonConfiguration(
      theme: google_web.GSIButtonTheme.outline,
      text: google_web.GSIButtonText.continueWith,
      shape: google_web.GSIButtonShape.pill,
      size: google_web.GSIButtonSize.large,
      minimumWidth: minimumWidth,
    ),
  );
}
