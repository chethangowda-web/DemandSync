import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../widgets/common.dart';
import 'help_screen.dart';
import 'history_screen.dart';
import 'home_screen.dart';
import 'track_screen.dart';

/// The signed-in app: Home, My Ration, History, Help. Nothing else lives in the bottom bar.
class Shell extends StatelessWidget {
  const Shell({super.key});

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final tabs = context.watch<TabIndex>();
    return Scaffold(
      body: IndexedStack(index: tabs.index, children: const [HomeScreen(), TrackScreen(), HistoryScreen(), HelpScreen()]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tabs.index,
        onDestinationSelected: tabs.go,
        destinations: [
          NavigationDestination(icon: const Icon(Icons.home_outlined), selectedIcon: const Icon(Icons.home_rounded), label: l.navHome),
          NavigationDestination(icon: const Icon(Icons.local_shipping_outlined), selectedIcon: const Icon(Icons.local_shipping_rounded), label: l.navMyRation),
          NavigationDestination(icon: const Icon(Icons.receipt_long_outlined), selectedIcon: const Icon(Icons.receipt_long_rounded), label: l.navHistory),
          NavigationDestination(icon: const Icon(Icons.support_agent_outlined), selectedIcon: const Icon(Icons.support_agent_rounded), label: l.navHelp),
        ],
      ),
    );
  }
}
