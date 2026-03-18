import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'screens/auth_screen.dart';
import 'screens/main_shell.dart';
import 'state/app_state.dart';
import 'theme/aura_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await dotenv.load(fileName: ".env");
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.transparent,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: AuraColors.backgroundDark,
  ));
  runApp(const EnglishTechApp());
}

class EnglishTechApp extends StatelessWidget {
  const EnglishTechApp({super.key, this.home});

  final Widget? home;

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider<AppState>(
      create: (_) => AppState(),
      child: MaterialApp(
        title: 'Aura – English Coach',
        debugShowCheckedModeBanner: false,
        theme: AuraTheme.dark,
        home: home ?? const _RootRouter(),
      ),
    );
  }
}

class _RootRouter extends StatelessWidget {
  const _RootRouter();

  @override
  Widget build(BuildContext context) {
    final state = context.watch<AppState>();

    if (state.loading) {
      return const Scaffold(
        backgroundColor: AuraColors.backgroundDark,
        body: Center(
          child: CircularProgressIndicator(color: AuraColors.primary),
        ),
      );
    }

    if (!state.isAuthenticated) {
      return const AuthScreen();
    }

    return const MainShell();
  }
}
