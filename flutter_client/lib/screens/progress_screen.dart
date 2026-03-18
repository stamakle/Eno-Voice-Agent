import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:percent_indicator/percent_indicator.dart';
import 'package:provider/provider.dart';
import 'package:shimmer/shimmer.dart';

import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import '../widgets/aura_widgets.dart';

class ProgressScreen extends StatelessWidget {
  const ProgressScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();
    final dash = state.dashboard;

    if (state.loading || dash == null) {
      return _buildSkeleton();
    }

    final double overallPct = (dash.totalCompletedLessons / 30).clamp(0.0, 1.0);

    return Container(
      decoration: const BoxDecoration(gradient: AuraColors.backgroundGradient),
      child: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 14),
              Text('Your Progress',
                  style: GoogleFonts.spaceGrotesk(
                      fontSize: 24, fontWeight: FontWeight.w800, color: AuraColors.textPrimary)),
              Text('Track your English journey', style: GoogleFonts.spaceGrotesk(fontSize: 14, color: AuraColors.textSecondary)),
              const SizedBox(height: 24),

              // Circular progress ring
              Center(
                child: CircularPercentIndicator(
                  radius: 90,
                  lineWidth: 12,
                  percent: overallPct,
                  center: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('${(overallPct * 100).round()}%',
                          style: GoogleFonts.spaceGrotesk(
                              fontSize: 32, fontWeight: FontWeight.w800, color: AuraColors.textPrimary)),
                      Text('Complete',
                          style: GoogleFonts.spaceGrotesk(fontSize: 12, color: AuraColors.textSecondary)),
                    ],
                  ),
                  progressColor: AuraColors.primary,
                  backgroundColor: AuraColors.borderDark,
                  circularStrokeCap: CircularStrokeCap.round,
                  animation: true,
                  animationDuration: 1200,
                ),
              ).animate().fadeIn(duration: 500.ms),

              const SizedBox(height: 28),

              // Stats row
              Row(
                children: [
                  Expanded(child: _StatCard(value: '${dash.totalCompletedLessons}', label: 'Lessons Done', icon: Icons.check_circle_outline)),
                  const SizedBox(width: 12),
                  Expanded(child: _StatCard(value: '${dash.reviewCountDue}', label: 'Reviews Due', icon: Icons.replay_outlined)),
                  const SizedBox(width: 12),
                  Expanded(child: _StatCard(value: state.levelBand[0].toUpperCase() + state.levelBand.substring(1), label: 'Level', icon: Icons.trending_up)),
                ],
              ).animate().fadeIn(delay: 200.ms),

              const SizedBox(height: 24),

              // Weak topics
              if (state.weakTopics.isNotEmpty) ...[
                Text('Areas to Improve',
                    style: GoogleFonts.spaceGrotesk(
                        fontSize: 18, fontWeight: FontWeight.w700, color: AuraColors.textPrimary)),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: state.weakTopics.asMap().entries.map((e) {
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: AuraColors.warning.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AuraColors.warning.withOpacity(0.3)),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.priority_high, color: AuraColors.warning, size: 14),
                          const SizedBox(width: 6),
                          Text(e.value,
                              style: const TextStyle(
                                  color: AuraColors.warning, fontSize: 13, fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ).animate().fadeIn(delay: Duration(milliseconds: e.key * 80)).slideX(begin: 0.1);
                  }).toList(),
                ),
                const SizedBox(height: 24),
              ],

              // Next review
              if (dash.nextReviewDueOn != null)
                GlassCard(
                  child: Row(
                    children: [
                      const Icon(Icons.calendar_today_outlined, color: AuraColors.primary, size: 22),
                      const SizedBox(width: 14),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Next Review Due',
                              style: GoogleFonts.spaceGrotesk(
                                  fontWeight: FontWeight.w700, color: AuraColors.textPrimary)),
                          Text(dash.nextReviewDueOn!,
                              style: const TextStyle(color: AuraColors.textSecondary, fontSize: 13)),
                        ],
                      ),
                    ],
                  ),
                ).animate().fadeIn(delay: 300.ms),

              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSkeleton() {
    return Container(
      decoration: const BoxDecoration(gradient: AuraColors.backgroundGradient),
      child: SafeArea(
        child: Shimmer.fromColors(
          baseColor: AuraColors.cardDark,
          highlightColor: AuraColors.surfaceDark,
          child: SingleChildScrollView(
             padding: const EdgeInsets.symmetric(horizontal: 20),
             child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                   const SizedBox(height: 14),
                   Container(width: 150, height: 32, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8))),
                   const SizedBox(height: 8),
                   Container(width: 100, height: 16, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(4))),
                   const SizedBox(height: 24),
                   Center(child: Container(width: 180, height: 180, decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle))),
                   const SizedBox(height: 28),
                   Row(
                      children: [
                         Expanded(child: Container(height: 100, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)))),
                         const SizedBox(width: 12),
                         Expanded(child: Container(height: 100, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)))),
                         const SizedBox(width: 12),
                         Expanded(child: Container(height: 100, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16)))),
                      ],
                   ),
                   const SizedBox(height: 24),
                   Container(height: 60, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(16))),
                ],
             ),
          ),
        ),
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.value, required this.label, required this.icon});

  final String value;
  final String label;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(14),
      child: Column(
        children: [
          Icon(icon, color: AuraColors.primary, size: 22),
          const SizedBox(height: 8),
          Text(value,
              style: GoogleFonts.spaceGrotesk(
                  fontSize: 20, fontWeight: FontWeight.w800, color: AuraColors.textPrimary)),
          const SizedBox(height: 2),
          Text(label,
              textAlign: TextAlign.center,
              style: const TextStyle(color: AuraColors.textSecondary, fontSize: 10)),
        ],
      ),
    );
  }
}
