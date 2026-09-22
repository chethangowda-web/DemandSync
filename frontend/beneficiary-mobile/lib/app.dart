import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/api_client.dart';
import 'core/session.dart';
import 'core/theme.dart';
import 'l10n/generated/app_localizations.dart';
import 'screens/login_screen.dart';
import 'screens/shell.dart';
import 'screens/welcome_screen.dart';
import 'widgets/common.dart';

class DemandSyncApp extends StatelessWidget {
  const DemandSyncApp({super.key, required this.api, required this.session});

  final ApiClient api;
  final SessionController session;

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiClient>.value(value: api),
        ChangeNotifierProvider<SessionController>.value(value: session),
        ChangeNotifierProvider<TabIndex>(create: (_) => TabIndex()),
      ],
      child: Consumer<SessionController>(
        builder: (context, s, _) => MaterialApp(
          // A new key when the user signs in or out discards every pushed screen, so nothing from one
          // session (or one beneficiary) can remain on screen in the next.
          key: ValueKey(s.loggedIn),
          title: 'DemandSYNC',
          debugShowCheckedModeBanner: false,
          theme: buildTheme(),
          locale: s.locale,
          supportedLocales: AppLocalizations.supportedLocales,
          localizationsDelegates: const [
            AppLocalizations.delegate,
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          home: s.loggedIn ? const Shell() : (s.expired ? const LoginScreen() : const WelcomeScreen()),
        ),
      ),
    );
  }
}
