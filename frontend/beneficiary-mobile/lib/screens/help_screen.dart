import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/session.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'assistant_screen.dart';
import 'grievance_screen.dart';

class HelpScreen extends StatelessWidget {
  const HelpScreen({super.key});

  Future<void> _signOut(BuildContext context) async {
    final l = tr(context);
    final ok = await confirmDialog(context, title: l.signOut, body: l.signOutConfirm, yes: l.signOut, no: l.cancel, danger: true);
    if (!ok || !context.mounted) return;
    final api = context.read<ApiClient>(), session = context.read<SessionController>(), tabs = context.read<TabIndex>();
    await api.logout(); // revokes the token on the server; the local session is cleared either way
    tabs.go(0);
    await session.signOut();
  }

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    return Scaffold(
      appBar: AppBar(title: Text(l.helpTitle), actions: const [LanguageButton()]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        SectionHeader(icon: Icons.support_agent_rounded, title: l.helpTitle, subtitle: l.helpSubtitle, badgeColor: AppColors.blue),
        const SizedBox(height: 14),
        _Tile(icon: Icons.smart_toy_outlined, color: AppColors.blue, title: l.assistantTitle, subtitle: l.assistantSubtitle, onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const AssistantScreen()))),
        _Tile(icon: Icons.report_gmailerrorred_rounded, color: AppColors.warn, title: l.raiseGrievance, subtitle: l.raiseGrievanceSub, onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const GrievanceScreen()))),
        _Tile(icon: Icons.list_alt_rounded, color: AppColors.good, title: l.myGrievances, onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => const MyGrievancesScreen()))),
        _Tile(icon: Icons.translate_rounded, color: AppColors.navy, title: l.language, onTap: () => LanguageButton.pick(context)),
        const SizedBox(height: 10),
        BigButton(label: l.signOut, icon: Icons.logout_rounded, style: BigButtonStyle.danger, onPressed: () => _signOut(context)),
        const SizedBox(height: 20),
        Text(l.helpFooter, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: AppColors.textMuted)),
      ]),
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({required this.icon, required this.title, required this.onTap, this.subtitle, this.color = AppColors.blue});
  final IconData icon;
  final String title;
  final String? subtitle;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final t = Theme.of(context).textTheme;
    return SectionCard(
      onTap: onTap,
      child: Row(children: [
        IconBadge(icon: icon, color: color),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: t.titleMedium),
            if (subtitle != null) Text(subtitle!, style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
          ]),
        ),
        const Icon(Icons.chevron_right_rounded, color: AppColors.textMuted),
      ]),
    );
  }
}
