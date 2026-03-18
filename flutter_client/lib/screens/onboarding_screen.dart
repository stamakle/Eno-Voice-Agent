import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import '../widgets/aura_widgets.dart';
import 'main_shell.dart';

/// The auto-start voice onboarding screen.
/// Aura greets the user automatically via TTS and asks them to pick a level
/// by speaking (or tapping). Once confirmed the user enters the main app.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  String? _selectedLevel;

  final List<Map<String, dynamic>> _levels = const [
    {
      'id': 'beginner',
      'label': 'Beginner',
      'subtitle': 'Just starting my English journey',
      'icon': Icons.school_outlined,
    },
    {
      'id': 'advanced',
      'label': 'Advanced',
      'subtitle': 'I can hold longer conversations',
      'icon': Icons.trending_up,
    },
    {
      'id': 'fluent',
      'label': 'Fluent',
      'subtitle': 'Polishing grammar & pronunciation',
      'icon': Icons.verified_outlined,
    },
  ];

  Future<void> _confirm() async {
    if (_selectedLevel == null) return;
    final state = context.read<AppState>();
    await state.selectLevel(_selectedLevel!);
    await state.completeOnboarding();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => const MainShell()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: AuraColors.backgroundGradient),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              children: [
                const SizedBox(height: 40),

                // Avatar + greeting
                AuraAvatar(state: 'speaking', size: 140)
                    .animate()
                    .fadeIn(duration: 600.ms)
                    .slideY(begin: -0.2),

                const SizedBox(height: 24),

                Text(
                  'Hi! I\'m Aura 👋',
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 30,
                    fontWeight: FontWeight.w800,
                    color: AuraColors.textPrimary,
                  ),
                ).animate().fadeIn(delay: 300.ms, duration: 500.ms),

                const SizedBox(height: 10),

                Text(
                  'Your personal English Coach.\nLet\'s find the right level for you.',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.spaceGrotesk(
                    fontSize: 16,
                    color: AuraColors.textSecondary,
                    height: 1.5,
                  ),
                ).animate().fadeIn(delay: 500.ms, duration: 500.ms),

                const SizedBox(height: 36),

                // Level cards
                Expanded(
                  child: ListView.separated(
                    itemCount: _levels.length,
                    separatorBuilder: (_, __) => const SizedBox(height: 12),
                    itemBuilder: (context, i) {
                      final lvl = _levels[i];
                      return LevelCard(
                        label: lvl['label'] as String,
                        subtitle: lvl['subtitle'] as String,
                        icon: lvl['icon'] as IconData,
                        selected: _selectedLevel == lvl['id'],
                        onTap: () => setState(() => _selectedLevel = lvl['id'] as String),
                      );
                    },
                  ),
                ),

                const SizedBox(height: 24),

                // Confirm CTA
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _selectedLevel != null && !state.loading ? _confirm : null,
                    style: ElevatedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                    ),
                    child: Text(
                      'Start Learning →',
                      style: GoogleFonts.spaceGrotesk(fontSize: 17, fontWeight: FontWeight.w700),
                    ),
                  ),
                ).animate().fadeIn(delay: 700.ms),

                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
