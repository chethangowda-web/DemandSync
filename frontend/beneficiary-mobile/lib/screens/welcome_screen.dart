import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../widgets/common.dart';
import 'login_screen.dart';

class WelcomeScreen extends StatelessWidget {
  const WelcomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [AppColors.navy, AppColors.blue])),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 24),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Align(alignment: Alignment.centerRight, child: LanguageButton()),
              const Spacer(),
              const Center(child: BrandMark(size: 96)),
              const SizedBox(height: 28),
              Text(l.appName, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 38, fontWeight: FontWeight.w800)),
              const SizedBox(height: 10),
              Text(l.appTagline, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFFCFE0FF), fontSize: 18, fontWeight: FontWeight.w600, height: 1.4)),
              const SizedBox(height: 22),
              Text(l.welcomeBody, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 16, height: 1.5)),
              const Spacer(),
              FilledButton(
                onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const LoginScreen())),
                style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(58), backgroundColor: Colors.white, foregroundColor: AppColors.navy, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)), textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800)),
                child: Text(l.getStarted),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}
