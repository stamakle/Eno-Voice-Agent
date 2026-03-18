import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AuraColors {
  static const Color primary = Color(0xFF25C0F4);
  static const Color backgroundDark = Color(0xFF101E22);
  static const Color surfaceDark = Color(0xFF172428);
  static const Color cardDark = Color(0xFF1E2F35);
  static const Color borderDark = Color(0xFF243840);
  static const Color textPrimary = Color(0xFFF1F5F9);
  static const Color textSecondary = Color(0xFF94A3B8);
  static const Color success = Color(0xFF22C55E);
  static const Color warning = Color(0xFFF59E0B);
  static const Color error = Color(0xFFEF4444);

  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primary, Color(0xFF0EA5E9)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient backgroundGradient = LinearGradient(
    colors: [Color(0xFF0D1B1E), Color(0xFF101E22), Color(0xFF14262B)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static BoxShadow get primaryGlow => BoxShadow(
        color: primary.withOpacity(0.35),
        blurRadius: 28,
        spreadRadius: 4,
      );

  static BoxShadow get subtleGlow => BoxShadow(
        color: primary.withOpacity(0.15),
        blurRadius: 16,
        spreadRadius: 2,
      );
}

class AuraTheme {
  static ThemeData get dark {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: AuraColors.backgroundDark,
      colorScheme: const ColorScheme.dark(
        primary: AuraColors.primary,
        surface: AuraColors.surfaceDark,
        onSurface: AuraColors.textPrimary,
        secondary: Color(0xFF0EA5E9),
      ),
      textTheme: GoogleFonts.spaceGroteskTextTheme(
        const TextTheme(
          displayLarge: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w700),
          displayMedium: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w700),
          headlineLarge: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w700),
          headlineMedium: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w600),
          titleLarge: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w600),
          titleMedium: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w500),
          bodyLarge: TextStyle(color: AuraColors.textPrimary),
          bodyMedium: TextStyle(color: AuraColors.textSecondary),
          labelLarge: TextStyle(color: AuraColors.textPrimary, fontWeight: FontWeight.w600),
        ),
      ),
      cardTheme: CardThemeData(
        color: AuraColors.cardDark,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AuraColors.borderDark),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AuraColors.cardDark,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AuraColors.borderDark),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AuraColors.borderDark),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: const BorderSide(color: AuraColors.primary, width: 2),
        ),
        labelStyle: const TextStyle(color: AuraColors.textSecondary),
        hintStyle: const TextStyle(color: AuraColors.textSecondary),
      ),
      bottomNavigationBarTheme: const BottomNavigationBarThemeData(
        backgroundColor: AuraColors.surfaceDark,
        selectedItemColor: AuraColors.primary,
        unselectedItemColor: AuraColors.textSecondary,
        type: BottomNavigationBarType.fixed,
        elevation: 0,
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        titleTextStyle: GoogleFonts.spaceGrotesk(
          color: AuraColors.textPrimary,
          fontSize: 20,
          fontWeight: FontWeight.w700,
        ),
        iconTheme: const IconThemeData(color: AuraColors.textPrimary),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AuraColors.primary,
          foregroundColor: AuraColors.backgroundDark,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          textStyle: GoogleFonts.spaceGrotesk(fontWeight: FontWeight.w700, fontSize: 15),
        ),
      ),
    );
  }
}
