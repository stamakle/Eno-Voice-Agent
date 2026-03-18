import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import '../widgets/aura_widgets.dart';
import 'onboarding_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  Future<void> _resetApp(BuildContext context) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    if (!context.mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute<void>(builder: (_) => const OnboardingScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final dash = state.dashboard;

    final levelColor = {
      'beginner': const Color(0xFF22C55E),
      'intermediate': const Color(0xFFF59E0B),
      'fluent': AuraColors.primary,
    }[state.levelBand] ?? AuraColors.primary;

    return Container(
      decoration: const BoxDecoration(gradient: AuraColors.backgroundGradient),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            children: [
              const SizedBox(height: 24),

              // Avatar + name
              Stack(
                alignment: Alignment.center,
                children: [
                  AuraAvatar(state: 'idle', size: 100),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: const BoxDecoration(
                        color: AuraColors.primary,
                        shape: BoxShape.circle,
                      ),
                      child: const Icon(Icons.edit, size: 14, color: AuraColors.backgroundDark),
                    ),
                  ),
                ],
              ).animate().fadeIn(duration: 400.ms),

              const SizedBox(height: 16),

              Text(state.displayName,
                  style: GoogleFonts.spaceGrotesk(
                      fontSize: 24, fontWeight: FontWeight.w800, color: AuraColors.textPrimary))
                  .animate().fadeIn(delay: 200.ms),

              const SizedBox(height: 8),

              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                decoration: BoxDecoration(
                  color: levelColor.withOpacity(0.12),
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: levelColor.withOpacity(0.4)),
                ),
                child: Text(
                  state.levelBand.toUpperCase(),
                  style: TextStyle(
                      color: levelColor, fontWeight: FontWeight.w700, fontSize: 12, letterSpacing: 1.5),
                ),
              ).animate().fadeIn(delay: 300.ms),

              const SizedBox(height: 28),

              // Stats
              Row(
                children: [
                  Expanded(child: _ProfileStat(value: '${dash?.totalCompletedLessons ?? 0}', label: 'Lessons')),
                  Expanded(child: _ProfileStat(value: '${dash?.reviewCountDue ?? 0}', label: 'Reviews')),
                  Expanded(child: _ProfileStat(value: '${state.weakTopics.length}', label: 'Weak Areas')),
                ],
              ).animate().fadeIn(delay: 400.ms),

              const SizedBox(height: 24),

              // Settings section
              GlassCard(
                child: Column(
                  children: [
                    _SettingsRow(
                      icon: Icons.person_outline,
                      label: 'Learner ID',
                      value: state.learnerId,
                    ),
                    const Divider(color: AuraColors.borderDark, height: 1),
                    _SettingsRow(
                      icon: Icons.language,
                      label: 'Current Level',
                      value: state.levelBand,
                    ),
                    const Divider(color: AuraColors.borderDark, height: 1),
                    const _ScenarioDropdown(),
                    const Divider(color: AuraColors.borderDark, height: 1),
                    const _SettingsRow(
                      icon: Icons.notifications_none_outlined,
                      label: 'Daily Goal',
                      value: '10 minutes',
                    ),
                    const Divider(color: AuraColors.borderDark, height: 1),
                    _SettingsRow(
                      icon: Icons.wifi,
                      label: 'Backend Status',
                      value: state.backendOnline ? 'Online ✓' : 'Offline ✗',
                      valueColor: state.backendOnline ? AuraColors.success : AuraColors.error,
                    ),
                  ],
                ),
              ).animate().fadeIn(delay: 500.ms),

              const SizedBox(height: 16),

              // Reset onboarding
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => _resetApp(context),
                  icon: const Icon(Icons.refresh, color: AuraColors.textSecondary),
                  label: Text('Reset & Re-onboard',
                      style: GoogleFonts.spaceGrotesk(color: AuraColors.textSecondary)),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: AuraColors.borderDark),
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                ),
              ).animate().fadeIn(delay: 600.ms),

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }
}

class _ProfileStat extends StatelessWidget {
  const _ProfileStat({required this.value, required this.label});

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(value,
            style: GoogleFonts.spaceGrotesk(
                fontSize: 26, fontWeight: FontWeight.w800, color: AuraColors.textPrimary)),
        Text(label, style: const TextStyle(color: AuraColors.textSecondary, fontSize: 12)),
      ],
    );
  }
}

class _SettingsRow extends StatelessWidget {
  const _SettingsRow({required this.icon, required this.label, required this.value, this.valueColor});

  final IconData icon;
  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        children: [
          Icon(icon, color: AuraColors.textSecondary, size: 20),
          const SizedBox(width: 14),
          Text(label,
              style: const TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w500)),
          const Spacer(),
          Text(value,
              style: TextStyle(
                  color: valueColor ?? AuraColors.textSecondary,
                  fontSize: 13,
                  fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }
}

class _ScenarioDropdown extends StatelessWidget {
  const _ScenarioDropdown();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final current = state.preferredScenario;
    final options = [
      'General conversation',
      'Job Interview',
      'Debate',
      'Travel & Tourism',
      'Academic Discussion'
    ];
    final value = options.contains(current) ? current : 'General conversation';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          const Icon(Icons.movie_filter_outlined, color: AuraColors.textSecondary, size: 20),
          const SizedBox(width: 14),
          const Text('Coach Roleplay',
              style: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w500)),
          const Spacer(),
          DropdownButton<String>(
            value: value,
            dropdownColor: AuraColors.backgroundDark,
            style: const TextStyle(color: AuraColors.textSecondary, fontSize: 13, fontWeight: FontWeight.w600),
            underline: const SizedBox(),
            items: options.map((String val) {
              return DropdownMenuItem<String>(
                value: val,
                child: Text(val),
              );
            }).toList(),
            onChanged: (String? newValue) {
              if (newValue != null && newValue != current) {
                context.read<AppState>().selectScenario(newValue);
              }
            },
          ),
        ],
      ),
    );
  }
}
