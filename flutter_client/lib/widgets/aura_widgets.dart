import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../theme/aura_theme.dart';

/// The pulsing Aura avatar circle shown in speaking / listening / analyzing states.
class AuraAvatar extends StatelessWidget {
  const AuraAvatar({
    super.key,
    required this.state,
    this.size = 180,
  });

  final String state; // 'idle' | 'speaking' | 'listening' | 'analyzing'
  final double size;

  @override
  Widget build(BuildContext context) {
    final isSpeaking = state == 'speaking';
    final isListening = state == 'listening';
    final isAnalyzing = state == 'analyzing';

    Color glowColor = AuraColors.primary;
    if (isListening) glowColor = const Color(0xFF22C55E);
    if (isAnalyzing) glowColor = const Color(0xFFF59E0B);

    Widget avatar = Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(
          colors: [
            glowColor.withOpacity(0.18),
            AuraColors.backgroundDark.withOpacity(0.0),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: glowColor.withOpacity(isSpeaking || isListening ? 0.5 : 0.2),
            blurRadius: isSpeaking ? 48 : 24,
            spreadRadius: isSpeaking ? 8 : 2,
          ),
        ],
      ),
      child: ClipOval(
        child: Image.asset(
          'assets/images/avatar.png',
          width: size,
          height: size,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => Container(
            width: size,
            height: size,
            color: AuraColors.surfaceDark,
            child: Icon(
              Icons.person_rounded,
              size: size * 0.5,
              color: AuraColors.primary,
            ),
          ),
        ),
      ),
    );

    // Outer ring
    avatar = Stack(
      alignment: Alignment.center,
      children: [
        Container(
          width: size + 20,
          height: size + 20,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: glowColor.withOpacity(0.4), width: 2),
          ),
        ),
        avatar,
      ],
    );

    if (isSpeaking) {
      avatar = avatar
          .animate(onPlay: (c) => c.repeat(reverse: true))
          .scaleXY(end: 1.06, duration: 600.ms, curve: Curves.easeInOut);
    } else if (isListening) {
      avatar = avatar
          .animate(onPlay: (c) => c.repeat(reverse: true))
          .scaleXY(end: 1.04, duration: 400.ms, curve: Curves.easeInOut)
          .shimmer(color: glowColor.withOpacity(0.2), duration: 800.ms);
    } else if (isAnalyzing) {
      avatar = avatar.animate(onPlay: (c) => c.repeat()).rotate(duration: 2000.ms);
    }

    return avatar;
  }
}

/// Status badge pill shown below the avatar (e.g. "Speaking…", "Listening…")
class AuraStatusBadge extends StatelessWidget {
  const AuraStatusBadge({super.key, required this.text, required this.color});

  final String text;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ).animate(onPlay: (c) => c.repeat(reverse: true)).fade(end: 0.2, duration: 600.ms),
          const SizedBox(width: 8),
          Text(text,
              style: TextStyle(
                  color: color, fontSize: 13, fontWeight: FontWeight.w600, letterSpacing: 0.4)),
        ],
      ),
    );
  }
}

/// A glass-morphism card used throughout the app.
class GlassCard extends StatelessWidget {
  const GlassCard({super.key, required this.child, this.padding, this.borderRadius});

  final Widget child;
  final EdgeInsets? padding;
  final double? borderRadius;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding ?? const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AuraColors.cardDark,
        borderRadius: BorderRadius.circular(borderRadius ?? 20),
        border: Border.all(color: AuraColors.borderDark),
        boxShadow: [AuraColors.subtleGlow],
      ),
      child: child,
    );
  }
}

/// Level selection card (Beginner / Intermediate / Fluent).
class LevelCard extends StatelessWidget {
  const LevelCard({
    super.key,
    required this.label,
    required this.subtitle,
    required this.icon,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final String subtitle;
  final IconData icon;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: selected ? AuraColors.primary.withOpacity(0.12) : AuraColors.cardDark,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
            color: selected ? AuraColors.primary : AuraColors.borderDark,
            width: selected ? 2 : 1,
          ),
          boxShadow: selected ? [AuraColors.subtleGlow] : [],
        ),
        child: Row(
          children: [
            Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: selected ? AuraColors.primary.withOpacity(0.2) : AuraColors.surfaceDark,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: selected ? AuraColors.primary : AuraColors.textSecondary),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(label,
                      style: TextStyle(
                          color: selected ? AuraColors.primary : AuraColors.textPrimary,
                          fontWeight: FontWeight.w700,
                          fontSize: 16)),
                  Text(subtitle, style: const TextStyle(color: AuraColors.textSecondary, fontSize: 12)),
                ],
              ),
            ),
            if (selected)
              const Icon(Icons.check_circle, color: AuraColors.primary, size: 22),
          ],
        ),
      ),
    ).animate().fadeIn(duration: 300.ms).slideY(begin: 0.1);
  }
}

/// Pulsing mic button for the lesson screen.
class MicButton extends StatelessWidget {
  const MicButton({
    super.key,
    required this.isRecording,
    required this.isProcessing,
    required this.onTap,
  });

  final bool isRecording;
  final bool isProcessing;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    Color bg = AuraColors.primary;
    IconData icon = Icons.mic;
    if (isRecording) {
      bg = const Color(0xFF22C55E);
      icon = Icons.stop;
    }
    if (isProcessing) {
      bg = const Color(0xFFF59E0B);
      icon = Icons.hourglass_empty;
    }

    final screenWidth = MediaQuery.of(context).size.width;
    final isCompact = screenWidth < 760;
    final size = isCompact ? 64.0 : 72.0;

    Widget btn = GestureDetector(
      onTap: isProcessing ? null : onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          color: bg,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
                color: bg.withValues(alpha: 0.4), blurRadius: 24, spreadRadius: 4)
          ],
        ),
        child: Icon(icon, color: AuraColors.backgroundDark, size: isCompact ? 26 : 30),
      ),
    );

    if (isRecording) {
      btn = btn
          .animate(onPlay: (c) => c.repeat(reverse: true))
          .scaleXY(end: 1.08, duration: 500.ms, curve: Curves.easeInOut)
          .shimmer(color: Colors.white.withOpacity(0.4), duration: 1000.ms);
    }

    return btn;
  }
}
