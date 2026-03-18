import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:shimmer/shimmer.dart';

import '../models/api_models.dart';
import '../state/app_state.dart';
import '../theme/aura_theme.dart';
import 'lesson_screen.dart';

class DiscoverScreen extends StatelessWidget {
  const DiscoverScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    return Container(
      decoration: const BoxDecoration(gradient: AuraColors.backgroundGradient),
      child: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
              sliver: SliverToBoxAdapter(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Discover Hub',
                        style: GoogleFonts.spaceGrotesk(
                            fontSize: 24, fontWeight: FontWeight.w800, color: AuraColors.textPrimary)),
                    Text('Choose your next lesson',
                        style: GoogleFonts.spaceGrotesk(
                            fontSize: 14, color: AuraColors.textSecondary)),
                  ],
                ),
              ),
            ),

            // Level filter chips
            SliverPadding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              sliver: SliverToBoxAdapter(
                child: Row(
                  children: ['All', 'Beginner', 'Intermediate', 'Fluent'].map((label) {
                    final active = label == 'All' || label.toLowerCase() == state.levelBand;
                    return Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 200),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                        decoration: BoxDecoration(
                          color: active ? AuraColors.primary : AuraColors.cardDark,
                          borderRadius: BorderRadius.circular(999),
                          border: Border.all(color: active ? AuraColors.primary : AuraColors.borderDark),
                        ),
                        child: Text(label,
                            style: TextStyle(
                                color: active ? AuraColors.backgroundDark : AuraColors.textSecondary,
                                fontWeight: FontWeight.w600,
                                fontSize: 13)),
                      ),
                    );
                  }).toList(),
                ),
              ),
            ),

            const SliverPadding(padding: EdgeInsets.only(top: 16)),

            // Course cards
            if (state.loading)
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                sliver: SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (context, i) => Padding(
                      padding: const EdgeInsets.only(bottom: 14),
                      child: Shimmer.fromColors(
                        baseColor: AuraColors.cardDark,
                        highlightColor: AuraColors.surfaceDark,
                        child: Container(
                          height: 96,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(20),
                          ),
                        ),
                      ),
                    ),
                    childCount: 4,
                  ),
                ),
              )
            else
              SliverPadding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                sliver: SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (context, i) {
                      final template = state.templates[i];
                      final isRecommended =
                          state.dashboard?.recommendedLesson?.courseId == template.courseId;
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 14),
                        child: _CourseCard(
                          template: template,
                          isRecommended: isRecommended,
                          onTap: () {
                            final lesson = state.dashboard?.recommendedLesson;
                            if (lesson == null || lesson.courseId != template.courseId) return;
                            Navigator.of(context).push(MaterialPageRoute<void>(
                              builder: (_) => LessonScreen(
                                courseId: lesson.courseId,
                                chapterId: lesson.chapterId,
                                lessonId: lesson.lessonId,
                              ),
                            ));
                          },
                        ),
                      ).animate().fadeIn(delay: Duration(milliseconds: i * 80)).slideY(begin: 0.1);
                    },
                    childCount: state.templates.length,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _CourseCard extends StatelessWidget {
  const _CourseCard({required this.template, required this.isRecommended, required this.onTap});

  final CourseTemplateSummary template;
  final bool isRecommended;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final levelIcons = {'beginner': Icons.school_outlined, 'intermediate': Icons.trending_up, 'fluent': Icons.verified_outlined};
    final icon = levelIcons[template.levelBand] ?? Icons.book_outlined;

    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AuraColors.cardDark,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: isRecommended ? AuraColors.primary : AuraColors.borderDark,
            width: isRecommended ? 2 : 1,
          ),
          boxShadow: isRecommended ? [AuraColors.subtleGlow] : [],
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                gradient: isRecommended ? AuraColors.primaryGradient : null,
                color: isRecommended ? null : AuraColors.surfaceDark,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(icon, color: isRecommended ? AuraColors.backgroundDark : AuraColors.textSecondary, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (isRecommended)
                    Container(
                      margin: const EdgeInsets.only(bottom: 6),
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AuraColors.primary.withOpacity(0.12),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text('Recommended',
                          style: TextStyle(color: AuraColors.primary, fontSize: 10, fontWeight: FontWeight.w700)),
                    ),
                  Text(template.title,
                      style: GoogleFonts.spaceGrotesk(
                          fontWeight: FontWeight.w700, color: AuraColors.textPrimary, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(template.levelBand.toUpperCase(),
                      style: const TextStyle(color: AuraColors.textSecondary, fontSize: 12, letterSpacing: 0.8)),
                ],
              ),
            ),
            Icon(
              isRecommended ? Icons.play_circle_fill : Icons.lock_outline,
              color: isRecommended ? AuraColors.primary : AuraColors.textSecondary,
              size: 28,
            ),
          ],
        ),
      ),
    );
  }
}
