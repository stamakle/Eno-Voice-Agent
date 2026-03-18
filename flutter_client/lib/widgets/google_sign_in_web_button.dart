import 'package:flutter/widgets.dart';

import 'google_sign_in_web_button_stub.dart'
    if (dart.library.html) 'google_sign_in_web_button_web.dart' as impl;

Widget buildGoogleSignInWebButton({double minimumWidth = 320}) {
  return impl.buildGoogleSignInWebButton(minimumWidth: minimumWidth);
}
