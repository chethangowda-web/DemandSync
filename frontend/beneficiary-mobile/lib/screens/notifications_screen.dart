import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// A read-only feed of real workflow events for the signed-in beneficiary, derived from the
/// same journey and grievance records shown on Home/Track/Help. No separate notification store.
class NotificationsScreen extends StatelessWidget {
  const NotificationsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final l = tr(context);
    final api = context.read<ApiClient>();
    return Scaffold(
      appBar: AppBar(title: Text(l.notificationsTitle), actions: const [LanguageButton()]),
      body: AsyncBody<List<AppNotification>>(
        load: api.notifications,
        builder: (context, items, reload) => RefreshIndicator(
          onRefresh: reload,
          child: items.isEmpty
              ? ListView(children: [
                  const SizedBox(height: 120),
                  Icon(Icons.notifications_none_rounded, size: 64, color: AppColors.textMuted.withValues(alpha: 0.7)),
                  const SizedBox(height: 14),
                  Center(child: Text(l.noNotifications, style: Theme.of(context).textTheme.titleMedium?.copyWith(color: AppColors.textMuted))),
                ])
              : ListView(padding: const EdgeInsets.all(16), children: [for (final n in items) _NotificationTile(item: n)]),
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({required this.item});
  final AppNotification item;

  @override
  Widget build(BuildContext context) {
    final loc = Localizations.localeOf(context).languageCode;
    final t = Theme.of(context).textTheme;
    final isException = item.kind == 'EXCEPTION';
    return SectionCard(
      onTap: () {
        final tabs = context.read<TabIndex>();
        Navigator.of(context).popUntil((r) => r.isFirst);
        tabs.go(item.view == 'track' ? 1 : (item.view == 'help' ? 3 : 0));
      },
      child: Row(children: [
        CircleAvatar(
          backgroundColor: isException ? AppColors.badSoft : AppColors.goodSoft,
          child: Icon(isException ? Icons.error_outline_rounded : Icons.notifications_active_outlined,
              color: isException ? AppColors.bad : AppColors.good),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(item.message, style: t.bodyLarge),
            if (item.at != null) Text(dateText(item.at!.toLocal(), loc), style: t.bodyMedium?.copyWith(color: AppColors.textMuted)),
          ]),
        ),
      ]),
    );
  }
}
