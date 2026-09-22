import 'package:flutter/material.dart';

/// Institutional blue on clean light surfaces. Every status also carries an icon and a word, never colour alone.
class AppColors {
  static const navy = Color(0xFF0B2A5B);
  static const blue = Color(0xFF1747B0);
  static const blueSoft = Color(0xFFE8EFFC);
  static const background = Color(0xFFF4F7FC);
  static const surface = Colors.white;
  static const border = Color(0xFFD9E1EF);
  static const text = Color(0xFF14213D);
  static const textMuted = Color(0xFF4B5A75);
  static const good = Color(0xFF13795B);
  static const goodSoft = Color(0xFFE3F5EE);
  static const warn = Color(0xFF9A5B00);
  static const warnSoft = Color(0xFFFFF1D6);
  static const bad = Color(0xFFB42318);
  static const badSoft = Color(0xFFFDE7E4);
}

ThemeData buildTheme() {
  final scheme = ColorScheme.fromSeed(seedColor: AppColors.blue, primary: AppColors.blue, surface: AppColors.surface);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.background,
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.navy,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
    ),
    textTheme: const TextTheme(
      headlineSmall: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: AppColors.text, height: 1.25),
      titleLarge: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: AppColors.text, height: 1.3),
      titleMedium: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: AppColors.text, height: 1.3),
      bodyLarge: TextStyle(fontSize: 17, color: AppColors.text, height: 1.4),
      bodyMedium: TextStyle(fontSize: 15, color: AppColors.text, height: 1.4),
      labelLarge: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: AppColors.border)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: AppColors.border)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: AppColors.blue, width: 2)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Colors.white,
      indicatorColor: AppColors.blueSoft,
      height: 72,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      labelTextStyle: WidgetStateProperty.all(const TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
    ),
    dividerColor: AppColors.border,
  );
}
