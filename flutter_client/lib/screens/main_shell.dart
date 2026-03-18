import 'package:flutter/material.dart';

import 'coach_screen.dart';

/// Public learner shell: the product is the coach itself.
/// Dashboard-style surfaces remain support-only and are intentionally omitted.
class MainShell extends StatelessWidget {
  const MainShell({super.key});

  @override
  Widget build(BuildContext context) {
    return const Scaffold(body: CoachScreen());
  }
}
